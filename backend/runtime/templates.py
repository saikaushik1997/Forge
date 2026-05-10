from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.agent import Agent
from models.workflow import Workflow

TEMPLATES = [
    {
        "workflow": {
            "name": "Research & Summarize",
            "description": "Searches the web for up-to-date information then distills it into a clear summary.",
        },
        "agents": [
            {
                "name": "Research Agent",
                "role": "Researcher",
                "system_prompt": (
                    "You are an expert research assistant with access to real-time web search. "
                    "When given a topic or question, search the web to find accurate, current information. "
                    "Cite your sources and be thorough but organized in your findings."
                ),
                "model": "claude-sonnet-4-6",
                "tools": ["web_search"],
                "guardrails": {"max_tokens": 2000},
            },
            {
                "name": "Summary Agent",
                "role": "Summarizer",
                "system_prompt": (
                    "You are a professional content summarizer. You receive research findings and distill them "
                    "into clear, concise, well-structured summaries. Use headers, bullet points, and tables "
                    "where appropriate. Focus on the most important insights."
                ),
                "model": "claude-sonnet-4-6",
                "tools": [],
                "guardrails": {"max_tokens": 1000},
            },
        ],
        "edges": [("Research Agent", "Summary Agent")],
        "positions": [(250, 80), (250, 280)],
    },
    {
        "workflow": {
            "name": "Triage & Respond",
            "description": "Classifies incoming requests by urgency and type, then drafts a professional response.",
        },
        "agents": [
            {
                "name": "Triage Agent",
                "role": "Triager",
                "system_prompt": (
                    "You are an intelligent triage agent. Analyze incoming requests, classify them by urgency "
                    "(Critical / High / Medium / Low), categorize by type, and provide a structured triage report "
                    "with routing recommendations. Be concise and use a consistent format."
                ),
                "model": "claude-sonnet-4-6",
                "tools": [],
                "guardrails": {"max_tokens": 500},
            },
            {
                "name": "Responder Agent",
                "role": "Responder",
                "system_prompt": (
                    "You are a professional customer success responder. Based on the triage analysis provided, "
                    "craft a clear, empathetic, and helpful response. Match the tone to the urgency level — "
                    "direct and action-oriented for critical issues, friendly and thorough for routine inquiries."
                ),
                "model": "claude-sonnet-4-6",
                "tools": [],
                "guardrails": {"max_tokens": 1500},
            },
        ],
        "edges": [("Triage Agent", "Responder Agent")],
        "positions": [(250, 80), (250, 280)],
    },
]


async def seed_templates(db: AsyncSession):
    existing = await db.execute(select(Workflow).where(Workflow.is_template == True))
    if existing.scalars().first():
        return  # already seeded

    for template in TEMPLATES:
        name_to_id: dict[str, str] = {}

        for i, agent_def in enumerate(template["agents"]):
            agent = Agent(
                name=agent_def["name"],
                role=agent_def["role"],
                system_prompt=agent_def["system_prompt"],
                model=agent_def["model"],
                tools=agent_def["tools"],
                guardrails=agent_def["guardrails"],
                memory_enabled=False,
            )
            db.add(agent)
            await db.flush()  # get the generated ID
            name_to_id[agent_def["name"]] = agent.id

        nodes = [
            {
                "id": f"node_{i}",
                "type": "agentNode",
                "position": {"x": template["positions"][i][0], "y": template["positions"][i][1]},
                "data": {"agent_id": name_to_id[a["name"]], "label": a["name"]},
            }
            for i, a in enumerate(template["agents"])
        ]

        name_to_node_id = {a["name"]: f"node_{i}" for i, a in enumerate(template["agents"])}
        edges = [
            {"id": f"e_{i}", "source": name_to_node_id[src], "target": name_to_node_id[tgt]}
            for i, (src, tgt) in enumerate(template["edges"])
        ]

        workflow = Workflow(
            name=template["workflow"]["name"],
            description=template["workflow"]["description"],
            graph_definition={"nodes": nodes, "edges": edges},
            is_template=True,
        )
        db.add(workflow)

    await db.commit()
    print("Template workflows seeded")
