# Forge
Build, configure, and orchestrate AI agents into collaborative workflows. Real LangGraph runtime, live execution logs, and Telegram integration — in one platform.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        Web UI (React)                       │
│   Agent CRUD · Visual Workflow Builder · Live Monitor       │
└─────────────────────────┬───────────────────────────────────┘
                          │ REST + WebSocket
┌─────────────────────────▼───────────────────────────────────┐
│                    Backend (FastAPI)                        │
│   Agent API · Workflow API · Execution API · Auth           │
└──────┬──────────────────┬──────────────────┬────────────────┘
       │                  │                  │
┌──────▼──────┐  ┌────────▼───────┐  ┌──────▼───────────────┐
│  LangGraph  │  │   PostgreSQL   │  │   Redis (pub/sub)    │
│  Runtime    │  │   Persistence  │  │   Async messaging    │
└──────┬──────┘  └────────────────┘  └──────────────────────┘
       │
┌──────▼──────────────────────────────────────────────────────┐
│                  Telegram Bot (python-telegram-bot)         │
│   Human ↔ Agent conversational interface                    │
└─────────────────────────────────────────────────────────────┘
```

Agents communicate asynchronously through Redis pub/sub. The LangGraph runtime manages agent state and tool execution. FastAPI persists everything to PostgreSQL and streams real-time logs to the UI via WebSocket.

---

## Stack Choices & Justifications

### Language: Python
The AI/ML ecosystem is Python-first. LangGraph, the Anthropic SDK, and every serious agent tooling library (web search, code execution, embeddings) have first-class Python support. Using Python means zero friction integrating these tools — no wrapper libraries, no translation layers.

### AI Runtime: LangGraph
LangGraph was chosen over CrewAI and AutoGen for two reasons:

1. **Control.** LangGraph models agent workflows as explicit state machines (nodes + edges). Conditions, feedback loops, and branching are first-class — exactly what the visual workflow builder needs to reflect. CrewAI abstracts this away, making it hard to expose configurability in a UI.
2. **Observability.** LangGraph's execution graph maps 1:1 to what we show in the UI. Every node execution, state transition, and tool call is inspectable, which powers the live monitoring dashboard.

AutoGen was ruled out because its conversational multi-agent model doesn't fit structured workflows with explicit routing conditions.

### Frontend: React + Vite
Plain React with Vite — no Next.js. Next.js adds server-side rendering and file-based routing, neither of which are needed here. This is a single-page app: a dashboard, a workflow canvas, a monitoring view. Vite gives a fast dev server and a simple static build that FastAPI serves directly. Less infrastructure, same result.

React Flow is used for the visual workflow builder. It handles the drag-and-drop canvas, node/edge rendering, and connection logic out of the box. Building an equivalent canvas from scratch would be a significant detour from the actual product work.

### Backend: FastAPI
FastAPI is async-native, which matters here — agent executions are long-running and the UI needs real-time updates via WebSocket. It also generates OpenAPI docs automatically, making the API self-documenting. Django and Flask were ruled out: Django is too heavy for an API-only backend, and Flask lacks native async support.

### Database: PostgreSQL (via Docker)
PostgreSQL runs fully locally inside Docker Compose alongside the other services — single command startup, no cloud dependency. It was chosen over SQLite because:

- Message history and workflow runs need relational queries (filter by agent, by workflow, by time range)
- Concurrent writes from multiple agent executions require proper row-level locking
- It's the realistic choice for a production-grade platform

### Async Messaging: Redis (pub/sub)
Agent-to-agent communication is asynchronous by requirement. The approach depends on scope:

**Within a single workflow**, LangGraph manages execution. Nodes run sequentially by default — this is intentional, giving deterministic and inspectable execution. Where true parallelism is needed (e.g. Research Bot and Fact-Check Bot running simultaneously), LangGraph's parallel branching runs those nodes concurrently and merges results before continuing.

**Across workflow boundaries**, Redis pub/sub handles async handoffs: incoming Telegram messages trigger workflow runs, completed runs stream events to the monitoring UI, and one workflow can trigger another — all without any component blocking on another. Redis runs as a Docker Compose service with no external dependency.

### Messaging Channel: Telegram
Telegram was chosen over Slack and WhatsApp because:

- **Slack** requires a paid workspace or workspace admin access to create bots with full permissions
- **WhatsApp** requires a Meta Business account and approval for the Cloud API
- **Telegram** bot creation is instant (BotFather, 30 seconds), the API is free, and `python-telegram-bot` is a well-maintained async library that integrates cleanly with FastAPI

---

## Features

- **Agent CRUD** — create agents with name, role, system prompt, model, tools, memory settings, and guardrails
- **Visual Workflow Builder** — drag-and-drop canvas (React Flow) to connect agents, set conditions, and build feedback loops
- **Pre-built Templates** — "Research & Summarize" and "Triage & Respond" workflows ready to use out of the box
- **Real Execution** — LangGraph actually runs agents; tool calls (web search, etc.) execute for real
- **Telegram Integration** — chat with a configured agent through Telegram; it can delegate to other agents behind the scenes
- **Live Monitoring** — real-time execution logs, inter-agent messages, and token/cost tracking streamed via WebSocket
- **Persistent History** — all runs, messages, and agent states stored in PostgreSQL and browsable in the UI

---

## Running Locally

### Prerequisites
- Docker + Docker Compose
- An Anthropic API key
- A Telegram bot token (from [@BotFather](https://t.me/botfather))

### Setup

```bash
git clone https://github.com/saikaushik1997/forge
cd forge
cp .env.example .env
# Fill in ANTHROPIC_API_KEY and TELEGRAM_BOT_TOKEN in .env
docker compose up
```

App is available at `http://localhost:3000`. API docs at `http://localhost:8000/docs`.

---

## Project Structure

```
forge/
├── backend/
│   ├── api/          # FastAPI route handlers
│   ├── runtime/      # LangGraph agent execution engine
│   ├── models/       # SQLAlchemy database models
│   └── channels/     # Telegram bot integration
├── frontend/
│   ├── src/
│   │   ├── pages/    # Dashboard, Agents, Workflows, Monitor
│   │   ├── components/
│   │   │   └── WorkflowCanvas.jsx  # React Flow canvas
│   │   └── api/      # API client
└── docker-compose.yml
```

---

## Adding a New Workflow Template

Templates are defined in [`backend/runtime/templates.py`](backend/runtime/templates.py) as entries in the `TEMPLATES` list.

1. Add a new entry to `TEMPLATES`:

```python
{
    "workflow": {
        "name": "My Template",
        "description": "What this pipeline does.",
    },
    "agents": [
        {
            "name": "Agent A",
            "role": "Role",
            "system_prompt": "You are ...",
            "model": "claude-sonnet-4-6",
            "tools": ["web_search"],   # web_search | calculator | datetime
            "guardrails": {"max_tokens": 1000},
        },
        # more agents...
    ],
    "edges": [("Agent A", "Agent B")],     # directed connections by agent name
    "positions": [(250, 80), (250, 280)],  # canvas (x, y) per agent
}
```

2. Clear the existing seeded templates so they re-seed on next startup:

```bash
docker exec -it forge-postgres-1 psql -U forge -d forge \
  -c "DELETE FROM workflows WHERE is_template = TRUE;"
```

3. Restart the backend — templates seed automatically at startup and appear in the UI under **Templates**.

---

## Adding a New Messaging Channel

Channel configuration is stored as JSON on each agent (`channel_configs`), so adding a new channel requires no database schema changes.

**1. Add UI fields** — open [`frontend/src/pages/Agents.jsx`](frontend/src/pages/Agents.jsx) and add the channel to `CHANNEL_FIELDS`:

```js
const CHANNEL_FIELDS = {
  telegram: [
    { key: "bot_token", label: "Bot Token", placeholder: "Token from @BotFather" },
  ],
  slack: [
    { key: "bot_token",       label: "Bot Token",       placeholder: "xoxb-..." },
    { key: "signing_secret",  label: "Signing Secret",  placeholder: "..." },
  ],
  // whatsapp, discord, etc.
};
```

The form renders fields automatically — no other frontend changes needed.

**2. Create a bot handler** — add `backend/bot/slack_bot.py` following the same structure as [`telegram_bot.py`](backend/bot/telegram_bot.py):
- Read agents where `channel_configs.slack.enabled == true`
- Decrypt `channel_configs.slack.bot_token` via `bot.crypto.decrypt_token`
- Start a polling/webhook listener per unique token

**3. Wire into the lifespan** — in [`backend/main.py`](backend/main.py), import and call your new `start_bots` / `stop_bots` alongside the Telegram ones.

**4. Add config to `.env`** if the channel needs additional app-level credentials (e.g. a Slack app token), and add the field to [`backend/config.py`](backend/config.py).

---

## Architecture Decisions: Tradeoffs

| Decision | Chosen | Rejected | Reason |
|---|---|---|---|
| AI Runtime | LangGraph | CrewAI, AutoGen | Explicit state machine maps to visual builder |
| Frontend | React + Vite | Next.js | No SSR needed, less overhead |
| Database | PostgreSQL | SQLite | Concurrent writes, relational queries |
| Channel | Telegram | Slack, WhatsApp | Instant setup, free API, async library |
| Async | Redis pub/sub | Celery, RabbitMQ | Simplest fit for pub/sub agent messaging |
