"""
Unit tests for the graph-building logic in runtime/templates.py.
Validates nodes/edges structure without touching the database.
"""
import pytest
from runtime.templates import TEMPLATES


@pytest.mark.parametrize("template", TEMPLATES)
def test_template_has_required_keys(template):
    assert "workflow" in template
    assert "agents" in template
    assert "edges" in template
    assert "positions" in template


@pytest.mark.parametrize("template", TEMPLATES)
def test_positions_match_agent_count(template):
    assert len(template["positions"]) == len(template["agents"])


@pytest.mark.parametrize("template", TEMPLATES)
def test_edges_reference_valid_agent_names(template):
    agent_names = {a["name"] for a in template["agents"]}
    for src, tgt in template["edges"]:
        assert src in agent_names, f"Edge source '{src}' not in agents"
        assert tgt in agent_names, f"Edge target '{tgt}' not in agents"


@pytest.mark.parametrize("template", TEMPLATES)
def test_each_agent_has_required_fields(template):
    required = {"name", "role", "system_prompt", "model", "tools", "guardrails"}
    for agent in template["agents"]:
        missing = required - agent.keys()
        assert not missing, f"Agent '{agent.get('name')}' missing fields: {missing}"


@pytest.mark.parametrize("template", TEMPLATES)
def test_guardrails_have_max_tokens(template):
    for agent in template["agents"]:
        assert "max_tokens" in agent["guardrails"], f"Agent '{agent['name']}' missing max_tokens guardrail"
        assert agent["guardrails"]["max_tokens"] > 0


def test_template_names_are_unique():
    names = [t["workflow"]["name"] for t in TEMPLATES]
    assert len(names) == len(set(names)), "Duplicate template workflow names"


def test_agent_names_unique_within_template():
    for template in TEMPLATES:
        names = [a["name"] for a in template["agents"]]
        assert len(names) == len(set(names)), f"Duplicate agent names in '{template['workflow']['name']}'"


@pytest.mark.parametrize("template", TEMPLATES)
def test_nodes_built_correctly(template):
    """Simulate the node-building logic from seed_templates and verify structure."""
    name_to_id = {a["name"]: f"fake-id-{i}" for i, a in enumerate(template["agents"])}
    nodes = [
        {
            "id": f"node_{i}",
            "type": "agentNode",
            "position": {"x": template["positions"][i][0], "y": template["positions"][i][1]},
            "data": {"agent_id": name_to_id[a["name"]], "label": a["name"]},
        }
        for i, a in enumerate(template["agents"])
    ]
    assert len(nodes) == len(template["agents"])
    for node in nodes:
        assert node["type"] == "agentNode"
        assert "agent_id" in node["data"]
        assert "label" in node["data"]
        assert "x" in node["position"] and "y" in node["position"]


@pytest.mark.parametrize("template", TEMPLATES)
def test_edges_built_correctly(template):
    """Simulate the edge-building logic from seed_templates and verify structure."""
    name_to_node_id = {a["name"]: f"node_{i}" for i, a in enumerate(template["agents"])}
    edges = [
        {"id": f"e_{i}", "source": name_to_node_id[src], "target": name_to_node_id[tgt]}
        for i, (src, tgt) in enumerate(template["edges"])
    ]
    assert len(edges) == len(template["edges"])
    for edge in edges:
        assert edge["source"].startswith("node_")
        assert edge["target"].startswith("node_")
        assert edge["source"] != edge["target"]
