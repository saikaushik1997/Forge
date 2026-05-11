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
    {
        "workflow": {
            "name": "Code Review Pipeline",
            "description": "Implements code, runs parallel security and performance reviews, iterates on feedback, then packages the approved result.",
        },
        "agents": [
            {
                "name": "Implementer",
                "role": "Developer",
                "system_prompt": (
                    "You are a senior software developer. When given a programming task, write clean, working Python code. "
                    "Be concise — provide the code and a brief explanation of key decisions."
                ),
                "model": "claude-sonnet-4-6",
                "tools": [],
                "guardrails": {"max_tokens": 1200},
            },
            {
                "name": "Security Reviewer",
                "role": "Security Engineer",
                "system_prompt": (
                    "You are a security engineer. Review the code provided for vulnerabilities such as path traversal, "
                    "injection, insecure defaults, and missing validation. Always start your response with 'SECURITY REVIEW:'. "
                    "Be concise and specific."
                ),
                "model": "claude-sonnet-4-6",
                "tools": [],
                "guardrails": {"max_tokens": 300},
            },
            {
                "name": "Performance Reviewer",
                "role": "Performance Engineer",
                "system_prompt": (
                    "You are a performance engineer. Review the code for performance issues such as blocking I/O, "
                    "inefficient loops, unnecessary memory allocation, and missing error handling. "
                    "Always start your response with 'PERFORMANCE REVIEW:'. Be concise and specific."
                ),
                "model": "claude-sonnet-4-6",
                "tools": [],
                "guardrails": {"max_tokens": 300},
            },
            {
                "name": "Lead Reviewer",
                "role": "Lead Engineer",
                "system_prompt": (
                    "You are a lead engineer conducting final code review. You will receive a security review and "
                    "performance review. If there are significant issues, respond starting with exactly 'REVISION NEEDED:' "
                    "followed by specific actionable feedback. If the code is acceptable, respond starting with exactly "
                    "'APPROVED:' followed by a brief comment. Be decisive."
                ),
                "model": "claude-sonnet-4-6",
                "tools": [],
                "guardrails": {"max_tokens": 300},
            },
            {
                "name": "Packager",
                "role": "Formatter",
                "system_prompt": (
                    "You receive a code implementation and a code review. Extract the final approved code and present "
                    "it cleanly. Format: show the code block first, then a 'Review Summary' section with the key points "
                    "from the security and performance reviews."
                ),
                "model": "claude-sonnet-4-6",
                "tools": [],
                "guardrails": {"max_tokens": 1500},
            },
        ],
        "edges": [
            ("Implementer", "Security Reviewer"),
            ("Implementer", "Performance Reviewer"),
            ("Security Reviewer", "Lead Reviewer"),
            ("Performance Reviewer", "Lead Reviewer"),
            {"source": "Lead Reviewer", "target": "Implementer", "condition": "revision needed", "type": "feedback"},
            {"source": "Lead Reviewer", "target": "Packager", "condition": "approved"},
        ],
        "positions": [(400, 50), (150, 250), (650, 250), (400, 450), (400, 650)],
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
        edges = []
        for i, e in enumerate(template["edges"]):
            if isinstance(e, tuple):
                src, tgt = e
                edge = {"id": f"e_{i}", "source": name_to_node_id[src], "target": name_to_node_id[tgt]}
            else:
                edge = {
                    "id": f"e_{i}",
                    "source": name_to_node_id[e["source"]],
                    "target": name_to_node_id[e["target"]],
                }
                if e.get("condition"):
                    edge["data"] = {"condition": e["condition"]}
                if e.get("type"):
                    edge["type"] = e["type"]
            edges.append(edge)

        workflow = Workflow(
            name=template["workflow"]["name"],
            description=template["workflow"]["description"],
            graph_definition={"nodes": nodes, "edges": edges},
            is_template=True,
        )
        db.add(workflow)

    await db.commit()
    print("Template workflows seeded")
