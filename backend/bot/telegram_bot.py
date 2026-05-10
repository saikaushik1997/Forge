import html
import asyncio
from collections import defaultdict

import anthropic
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from sqlalchemy import select

from config import settings
from database import AsyncSessionLocal
from models.agent import Agent
from runtime.engine import TOOL_DEFINITIONS, execute_tool
from bot.crypto import decrypt_token

# conversation history: {(agent_id, chat_id): [messages]}
_histories: dict[tuple, list] = defaultdict(list)


async def _get_telegram_agents() -> list[Agent]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Agent))
        return [
            a for a in result.scalars().all()
            if (a.channel_configs or {}).get("telegram", {}).get("enabled")
            and (a.channel_configs or {}).get("telegram", {}).get("bot_token")
        ]


def _build_app(agent: Agent, token: str) -> Application:
    app = Application.builder().token(token).build()
    app.bot_data["agent"] = agent

    app.add_handler(CommandHandler("start", _cmd_start))
    app.add_handler(CommandHandler("reset", _cmd_reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _handle_message))
    return app


async def _cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    agent: Agent = context.bot_data["agent"]
    await update.message.reply_text(
        f"⚡ <b>{html.escape(agent.name)}</b>\n"
        f"<i>{html.escape(agent.role)}</i>\n\n"
        "Send me a message to get started.\n"
        "/reset — clear conversation history",
        parse_mode="HTML",
    )


async def _cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    agent: Agent = context.bot_data["agent"]
    key = (agent.id, update.effective_chat.id)
    _histories[key] = []
    await update.message.reply_text("Conversation cleared.")


async def _handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    agent: Agent = context.bot_data["agent"]
    chat_id = update.effective_chat.id
    key = (agent.id, chat_id)
    user_text = update.message.text

    _histories[key].append({"role": "user", "content": user_text})

    thinking_msg = await update.message.reply_text("⏳ Thinking…")

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    tool_names = agent.tools or []
    tools = [TOOL_DEFINITIONS[t] for t in tool_names if t in TOOL_DEFINITIONS]
    max_tokens = (agent.guardrails or {}).get("max_tokens", 1024)

    messages = list(_histories[key])
    first_call = True
    output = ""

    try:
        while True:
            kwargs = dict(
                model=agent.model,
                max_tokens=max_tokens,
                system=agent.system_prompt,
                messages=messages,
            )
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = {"type": "any"} if first_call else {"type": "auto"}
            first_call = False

            response = await client.messages.create(**kwargs)

            if response.stop_reason == "end_turn":
                for block in response.content:
                    if block.type == "text":
                        output = block.text
                break

            if response.stop_reason == "tool_use":
                messages.append({"role": "assistant", "content": response.content})
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        result = await asyncio.get_running_loop().run_in_executor(
                            None, execute_tool, block.name, block.input
                        )
                        tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": result})
                messages.append({"role": "user", "content": tool_results})
            else:
                break

        _histories[key].append({"role": "assistant", "content": output})

        chunks = [output[i: i + 4000] for i in range(0, max(len(output), 1), 4000)]
        await thinking_msg.edit_text(chunks[0])
        for chunk in chunks[1:]:
            await update.message.reply_text(chunk)

    except Exception as e:
        await thinking_msg.edit_text(f"❌ Error: {html.escape(str(e))}", parse_mode="HTML")


async def start_bots() -> list[Application]:
    agents = await _get_telegram_agents()
    if not agents:
        return []

    started = []
    seen_tokens = set()

    for agent in agents:
        try:
            raw = agent.channel_configs["telegram"]["bot_token"]
            token = decrypt_token(raw) if settings.forge_encryption_key else raw
        except Exception:
            print(f"Failed to decrypt token for agent {agent.name}, skipping")
            continue

        if token in seen_tokens:
            print(f"Duplicate token for agent {agent.name}, skipping")
            continue
        seen_tokens.add(token)

        app = _build_app(agent, token)
        await app.initialize()
        await app.start()
        await app.updater.start_polling()
        started.append(app)
        print(f"Telegram bot started for agent: {agent.name}")

    return started


async def stop_bots(apps: list[Application]):
    for app in apps:
        try:
            await app.updater.stop()
            await app.stop()
            await app.shutdown()
        except Exception:
            pass
