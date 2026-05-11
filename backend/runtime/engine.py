import os
import re
import asyncio
from collections import defaultdict
from datetime import datetime
from typing import TypedDict, Annotated
import operator

import anthropic
from langgraph.graph import StateGraph, END

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from models.run import Message
from models.workflow import Workflow
from config import settings


MAX_LOOP_ITERATIONS = 3

INJECTION_PATTERNS = [
    "ignore previous instructions",
    "ignore your instructions",
    "disregard your system prompt",
    "forget your instructions",
    "new instructions:",
    "you are now",
    "act as if you",
    "pretend you are",
    "jailbreak",
    "dan mode",
]

MODEL_PRICING = {
    "claude-opus-4-7":           {"input": 15.0,  "output": 75.0},
    "claude-sonnet-4-6":         {"input": 3.0,   "output": 15.0},
    "claude-haiku-4-5-20251001": {"input": 0.80,  "output": 4.0},
}


def _compute_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    pricing = MODEL_PRICING.get(model, {"input": 3.0, "output": 15.0})
    return (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000


class AgentState(TypedDict):
    messages: Annotated[list, operator.add]       # initial user msg + all assistant msgs
    agent_outputs: Annotated[list, operator.add]  # {"agent": name, "content": text} per node
    run_id: str
    token_count: Annotated[int, operator.add]
    loop_count: Annotated[int, operator.add]      # increments each node execution; caps feedback loops
    cost: Annotated[float, operator.add]


def _find_back_edges(nodes: list, edges: list) -> set:
    """DFS to find back edges — edges that create cycles."""
    adj = defaultdict(list)
    for e in edges:
        adj[e["source"]].append(e["target"])

    visited, rec_stack, back_edges = set(), set(), set()

    def dfs(node):
        visited.add(node)
        rec_stack.add(node)
        for nb in adj[node]:
            if nb not in visited:
                dfs(nb)
            elif nb in rec_stack:
                back_edges.add((node, nb))
        rec_stack.discard(node)

    for n in nodes:
        if n["id"] not in visited:
            dfs(n["id"])

    return back_edges


def _make_router(outgoing: list, back_edge_pairs: set):
    """Return a LangGraph routing function for a node with conditions or cycles."""
    def router(state: AgentState):
        output = state["agent_outputs"][-1]["content"] if state["agent_outputs"] else ""
        loop_count = state.get("loop_count", 0)

        # Separate back edges from forward edges
        forward = [e for e in outgoing if (e["source"], e["target"]) not in back_edge_pairs]
        eligible = forward if loop_count >= MAX_LOOP_ITERATIONS else outgoing

        # Conditional edges first (keyword matching)
        for e in eligible:
            if e.get("condition") and e["condition"].lower() in output.lower():
                return e["target"]

        # Unconditional edges
        for e in eligible:
            if not e.get("condition"):
                return e["target"]

        return END

    return router


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
    guardrails = agent_config.get("guardrails", {})
    max_tokens = guardrails.get("max_tokens", 2000)
    max_tool_rounds = guardrails.get("max_tool_calls", 5)
    banned_phrases = [p.lower() for p in guardrails.get("banned_phrases", []) if p]
    injection_detection = guardrails.get("prompt_injection_detection", False)

    system_prompt = agent_config["system_prompt"]
    if tools:
        tool_list = ", ".join(t["name"] for t in tools)
        system_prompt += f"\n\nYou have access to these tools: {tool_list}. Always use them to get accurate, up-to-date information rather than relying on training data."
    if agent_config.get("past_messages"):
        memory_block = "\n\n---\n\n".join(agent_config["past_messages"])
        system_prompt += f"\n\n## Memory from previous runs\nThese are your past responses — use them as context for continuity:\n{memory_block}"

    async def node(state: AgentState) -> dict:
        await on_event({"type": "node_start", "agent": agent_config["name"], "run_id": run_id})

        # Fan-in: concatenate all prior agent outputs; entry node uses initial user message
        if state["agent_outputs"]:
            input_content = "\n\n---\n\n".join(o["content"] for o in state["agent_outputs"])
        else:
            input_content = state["messages"][0]["content"]

        if injection_detection:
            lower = input_content.lower()
            if any(p in lower for p in INJECTION_PATTERNS):
                matched = next(p for p in INJECTION_PATTERNS if p in lower)
                output = f"[BLOCKED: Prompt injection detected — '{matched}']"
                await on_event({"type": "node_complete", "agent": agent_config["name"], "output": output, "tokens": 0, "cost": 0.0, "run_id": run_id})
                return {
                    "agent_outputs": [{"agent": agent_config["name"], "content": output}],
                    "messages": [{"role": "assistant", "agent": agent_config["name"], "content": output}],
                    "token_count": 0,
                    "loop_count": 1,
                    "cost": 0.0,
                }

        messages = [{"role": "user", "content": input_content}]
        total_tokens = 0
        output = ""
        first_call = True
        tool_rounds = 0

        total_cost = 0.0
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
            in_tok = response.usage.input_tokens
            out_tok = response.usage.output_tokens
            total_tokens += in_tok + out_tok
            total_cost += _compute_cost(agent_config["model"], in_tok, out_tok)

            if response.stop_reason == "end_turn":
                for block in response.content:
                    if block.type == "text":
                        output = block.text
                if not output:
                    output = input_content
                break

            if response.stop_reason == "tool_use":
                tool_rounds += 1
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

                if tool_rounds >= max_tool_rounds:
                    kwargs.pop("tools", None)
                    kwargs.pop("tool_choice", None)
                    first_call = False
            else:
                # max_tokens or any other stop reason — extract whatever text was generated
                for block in response.content:
                    if block.type == "text":
                        output = block.text
                if not output:
                    output = input_content
                break

        for phrase in banned_phrases:
            output = re.sub(re.escape(phrase), "[REDACTED]", output, flags=re.IGNORECASE)

        await on_event({"type": "node_complete", "agent": agent_config["name"], "output": output, "tokens": total_tokens, "cost": total_cost, "run_id": run_id})

        return {
            "agent_outputs": [{"agent": agent_config["name"], "content": output}],
            "messages": [{"role": "assistant", "agent": agent_config["name"], "content": output}],
            "token_count": total_tokens,
            "loop_count": 1,
            "cost": total_cost,
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

    # Inject memory for enabled agents before building the graph
    for node in nodes:
        agent = agents_map.get(node["data"]["agent_id"])
        if agent and agent.get("memory_enabled"):
            result = await db.execute(
                select(Message)
                .where(Message.to_agent == agent["name"])
                .order_by(desc(Message.timestamp))
                .limit(5)
            )
            past = list(reversed(result.scalars().all()))
            agent["past_messages"] = [m.content for m in past]

    back_edge_pairs = _find_back_edges(nodes, edges)
    edges_by_source = defaultdict(list)
    for e in edges:
        edges_by_source[e["source"]].append(e)

    entry = nodes[0]["id"]
    builder.set_entry_point(entry)

    for node in nodes:
        node_id = node["id"]
        outgoing = edges_by_source[node_id]
        has_condition = any(e.get("condition") for e in outgoing)
        has_back_edge = any((node_id, e["target"]) in back_edge_pairs for e in outgoing)

        if not outgoing:
            builder.add_edge(node_id, END)
        elif has_condition or has_back_edge:
            router = _make_router(outgoing, back_edge_pairs)
            targets = {e["target"]: e["target"] for e in outgoing}
            targets[END] = END
            builder.add_conditional_edges(node_id, router, targets)
        else:
            for e in outgoing:
                builder.add_edge(e["source"], e["target"])

    graph = builder.compile()

    final_state = await graph.ainvoke({
        "messages": [{"role": "user", "content": run_input}],
        "agent_outputs": [],
        "run_id": run_id,
        "token_count": 0,
        "loop_count": 0,
        "cost": 0.0,
    })

    prev_agent = "user"
    for msg in final_state["messages"]:
        if msg["role"] == "assistant":
            db.add(Message(run_id=run_id, from_agent=prev_agent, to_agent=msg["agent"], content=msg["content"], tokens_used=0))
            prev_agent = msg["agent"]

    await db.commit()
    return final_state
