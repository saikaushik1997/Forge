import os
import asyncio
from datetime import datetime
from typing import TypedDict

import anthropic
from langgraph.graph import StateGraph, END

from sqlalchemy.ext.asyncio import AsyncSession
from models.run import Message
from models.workflow import Workflow
from config import settings


class AgentState(TypedDict):
    messages: list
    current_output: str
    run_id: str
    token_count: int


TOOL_DEFINITIONS = {
    "web_search": {
        "name": "web_search",
        "description": "Search the web for current, real-time information on any topic.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Search query"}},
            "required": ["query"],
        },
    },
    "calculator": {
        "name": "calculator",
        "description": "Evaluate a basic mathematical expression.",
        "input_schema": {
            "type": "object",
            "properties": {"expression": {"type": "string", "description": "Math expression e.g. '2 + 2'"}},
            "required": ["expression"],
        },
    },
    "datetime": {
        "name": "get_current_datetime",
        "description": "Get the current UTC date and time.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
}


def execute_tool(name: str, input_data: dict) -> str:
    if name == "web_search":
        os.environ["TAVILY_API_KEY"] = settings.tavily_api_key
        from langchain_community.tools.tavily_search import TavilySearchResults
        results = TavilySearchResults(max_results=3).invoke(input_data.get("query", ""))
        if isinstance(results, list):
            return "\n\n".join(f"[{r['url']}]\n{r['content']}" for r in results)
        return str(results)
    elif name == "calculator":
        try:
            return str(eval(input_data.get("expression", ""), {"__builtins__": {}}, {}))
        except Exception as e:
            return f"Error: {e}"
    elif name == "get_current_datetime":
        return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    return f"Unknown tool: {name}"


def make_agent_node(agent_config: dict, run_id: str, on_event):
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    tool_names = agent_config.get("tools", [])
    tools = [TOOL_DEFINITIONS[t] for t in tool_names if t in TOOL_DEFINITIONS]
    max_tokens = agent_config.get("guardrails", {}).get("max_tokens", 2000)

    system_prompt = agent_config["system_prompt"]
    if tools:
        tool_list = ", ".join(t["name"] for t in tools)
        system_prompt += f"\n\nYou have access to these tools: {tool_list}. Always use them to get accurate, up-to-date information rather than relying on training data."

    async def node(state: AgentState) -> AgentState:
        await on_event({"type": "node_start", "agent": agent_config["name"], "run_id": run_id})

        messages = [{"role": "user", "content": state["current_output"]}]
        total_tokens = 0
        output = ""
        first_call = True

        while True:
            kwargs = dict(
                model=agent_config["model"],
                max_tokens=max_tokens,
                system=system_prompt,
                messages=messages,
            )
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = {"type": "any"} if first_call else {"type": "auto"}
            first_call = False

            response = await client.messages.create(**kwargs)
            total_tokens += response.usage.input_tokens + response.usage.output_tokens

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
                        await on_event({"type": "tool_call", "agent": agent_config["name"], "tool": block.name, "run_id": run_id})
                        result = await asyncio.get_running_loop().run_in_executor(
                            None, execute_tool, block.name, block.input
                        )
                        tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": result})

                messages.append({"role": "user", "content": tool_results})
            else:
                # Unexpected stop reason
                break

        await on_event({"type": "node_complete", "agent": agent_config["name"], "output": output, "tokens": total_tokens, "run_id": run_id})

        return {
            **state,
            "current_output": output,
            "messages": state["messages"] + [{"role": "assistant", "agent": agent_config["name"], "content": output}],
            "token_count": state["token_count"] + total_tokens,
        }

    node.__name__ = agent_config["name"]
    return node


async def execute_workflow(workflow, agents_map, run_input, run_id, on_event, db):
    graph_def = workflow.graph_definition
    nodes = graph_def.get("nodes", [])
    edges = graph_def.get("edges", [])

    if not nodes:
        raise ValueError("Workflow has no nodes")

    builder = StateGraph(AgentState)

    for node in nodes:
        agent_id = node["data"]["agent_id"]
        agent = agents_map.get(agent_id)
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")
        builder.add_node(node["id"], make_agent_node(agent, run_id, on_event))

    for edge in edges:
        builder.add_edge(edge["source"], edge["target"])

    entry = nodes[0]["id"]
    builder.set_entry_point(entry)

    sources = {e["source"] for e in edges}
    for node in nodes:
        if node["id"] not in sources:
            builder.add_edge(node["id"], END)

    graph = builder.compile()

    final_state = await graph.ainvoke({
        "messages": [{"role": "user", "content": run_input}],
        "current_output": run_input,
        "run_id": run_id,
        "token_count": 0,
    })

    prev_agent = "user"
    for msg in final_state["messages"]:
        if msg["role"] == "assistant":
            db.add(Message(run_id=run_id, from_agent=prev_agent, to_agent=msg["agent"], content=msg["content"], tokens_used=0))
            prev_agent = msg["agent"]

    await db.commit()
    return final_state
