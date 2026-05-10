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

Within a workflow, LangGraph manages async agent execution — sequential by default, parallel where the graph fans out. Redis pub/sub handles cross-system async: Telegram → workflow triggers, and run events → WebSocket → UI. FastAPI persists everything to PostgreSQL.

---

## Stack Choices & Justifications

### Language: Python
The AI/ML ecosystem is Python-first. LangGraph, the Anthropic SDK, and every serious agent tooling library (web search, code execution, embeddings) have first-class Python support. Using Python means zero friction integrating these tools — no wrapper libraries, no translation layers.

### AI Runtime: LangGraph
LangGraph was chosen over CrewAI and AutoGen for three reasons:

1. **Control.** LangGraph models agent workflows as explicit state machines (nodes + edges). Conditions, feedback loops, and branching are first-class — exactly what the visual workflow builder needs to reflect. CrewAI abstracts this away, making it hard to expose configurability in a UI.
2. **Observability.** LangGraph's execution graph maps 1:1 to what we show in the UI. Every node execution, state transition, and tool call is inspectable, which powers the live monitoring dashboard.
3. **Native async parallelism.** When the workflow graph fans out to multiple nodes with no dependency between them (e.g. A → B and A → C), LangGraph executes them concurrently via `asyncio.gather` — no extra infrastructure needed. The shared `AgentState` uses `Annotated[list, operator.add]` reducers so concurrent writes merge safely rather than overwriting each other. The fan-in node (D) then receives the combined outputs of all parallel branches.

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
There are two distinct layers of async communication in Forge, and it's worth being precise about which handles what.

**Within a workflow**, async is handled entirely by LangGraph — not Redis. Each agent node is an `async` function. Sequential nodes run one after another (deterministic, inspectable). Parallel branches (when the graph fans out) run concurrently via `asyncio.gather`, with `Annotated` state reducers merging their outputs safely. No message broker is needed here; LangGraph's state machine is the transport.

**Across the system boundary**, Redis pub/sub handles async handoffs: incoming Telegram messages trigger workflow runs without blocking the bot, completed runs stream events to the monitoring UI via WebSocket, and external triggers (scheduled jobs, webhooks) can fire workflows without coupling to the HTTP layer. Redis runs as a Docker Compose service with no external dependency.

The alternative — routing all agent-to-agent communication through Redis queues — would mean rebuilding LangGraph's orchestration from scratch (delivery guarantees, fan-in coordination, error propagation) for no observable benefit in a single-host deployment.

### Messaging Channel: Telegram
Telegram was chosen over Slack and WhatsApp because:

- **Slack** requires a paid workspace or workspace admin access to create bots with full permissions
- **WhatsApp** requires a Meta Business account and approval for the Cloud API
- **Telegram** bot creation is instant (BotFather, 30 seconds), the API is free, and `python-telegram-bot` is a well-maintained async library that integrates cleanly with FastAPI

---

## Features

**Agents**
- Full CRUD — name, role, system prompt, model, tools, guardrails (max tokens), memory toggle, messaging channel config
- **Memory** — when enabled, the agent's last 5 outputs from past runs are injected into its system prompt at execution time, giving it continuity across separate workflow runs
- **Tools** — web search (Tavily), calculator, datetime; tool calls are real, not simulated
- **Telegram integration** — configure a bot token per agent; the agent becomes conversational with per-chat history and `/start` / `/reset` commands

**Workflows**
- **Visual builder** — drag-and-drop canvas (React Flow); arrowheads show direction; start node highlighted green, end nodes red; select + Backspace to delete nodes or edges
- **Conditional edges** — click any edge to set a keyword condition; the engine only follows that edge if the keyword appears in the upstream agent's output
- **Feedback loops** — draw a backward edge to create a cycle; the engine detects it via DFS and caps iterations at 3 before forcing the forward path
- **Parallel execution** — when multiple agents have no dependency between them, LangGraph runs them concurrently via `asyncio.gather`; a fan-in agent receives all their combined outputs
- **Schedules** — attach cron triggers to any workflow (⏰ button); the scheduler fires runs in the background with a configurable default input
- **Pre-built templates** — "Research & Summarize" and "Triage & Respond" seeded on startup; "Use Template" clones them into editable copies

**Platform**
- **Live monitoring** — real-time execution events (node start, tool calls, node complete) streamed via WebSocket; inter-agent messages and token counts visible per run
- **Persistent history** — all runs, messages, and agent outputs stored in PostgreSQL and browsable in the Monitor page

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

## Running Tests

46 tests across two suites. All pass against a running stack.

| Suite | File | Tests | Needs server? |
|---|---|---|---|
| Unit | `test_unit_crypto.py` | 5 | No |
| Unit | `test_unit_agent_configs.py` | 11 | No |
| Unit | `test_unit_templates.py` | 16 | No |
| Integration | `test_agents.py` | 9 | Yes |
| Integration | `test_workflow_execution.py` | 5 | Yes + API key |

**Unit tests** — no server, no API key, run in ~1s:

```bash
cd backend
pytest tests/test_unit_crypto.py tests/test_unit_agent_configs.py tests/test_unit_templates.py -v
```

Covers: Fernet encrypt/decrypt roundtrips, channel config masking and encryption helpers, template graph structure and edge validation.

**Integration tests** — hit a live backend at `localhost:8001`:

```bash
# Start the stack first
docker compose up -d

cd backend
pytest tests/test_agents.py tests/test_workflow_execution.py -v
```

Covers: full agent CRUD lifecycle, workflow run completion, token accounting, inter-agent message persistence, 404 error handling.

**Run everything:**

```bash
cd backend && pytest -v
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
| AI Runtime | LangGraph | CrewAI, AutoGen | Explicit state machine maps to visual builder; native parallel execution |
| Frontend | React + Vite | Next.js | No SSR needed, less overhead |
| Database | PostgreSQL | SQLite | Concurrent writes, relational queries |
| Channel | Telegram | Slack, WhatsApp | Instant setup, free API, async library |
| Async (intra-workflow) | LangGraph state machine | Redis queues | Already orchestrates execution; Redis would duplicate work |
| Async (cross-system) | Redis pub/sub | Celery, RabbitMQ | Simplest fit for pub/sub; no worker processes needed |
| Memory storage | PostgreSQL (Message table) | Redis / vector DB | Data already there; simple recency window is sufficient for now |
| Scheduling | croniter + asyncio loop | APScheduler, Celery Beat | No extra dependencies; fits cleanly in FastAPI lifespan |
| Feedback loop termination | loop_count in LangGraph state | External flag / timeout | State is already shared across nodes; incrementing a counter is zero overhead |
| Conditional routing | Keyword matching in output | LLM-based routing | Deterministic, fast, no extra API calls; sufficient for structured agent prompts |
