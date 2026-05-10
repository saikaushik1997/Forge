import pytest

AGENT_PAYLOAD = {
    "name": "Test Agent",
    "role": "Tester",
    "system_prompt": "You are a test agent. Reply with one word.",
    "model": "claude-sonnet-4-6",
    "tools": [],
    "guardrails": {"max_tokens": 50},
}


async def _create(client) -> dict:
    r = await client.post("/api/agents/", json=AGENT_PAYLOAD)
    assert r.status_code == 201
    return r.json()


async def _delete(client, agent_id: str):
    await client.delete(f"/api/agents/{agent_id}")


# ── Create ────────────────────────────────────────────────────────────────────

async def test_create_agent_returns_201(client):
    agent = await _create(client)
    assert agent["name"] == AGENT_PAYLOAD["name"]
    assert agent["role"] == AGENT_PAYLOAD["role"]
    assert "id" in agent
    await _delete(client, agent["id"])


async def test_create_agent_defaults(client):
    agent = await _create(client)
    assert agent["tools"] == []
    assert agent["memory_enabled"] is False
    assert agent["channel_configs"] == {}
    await _delete(client, agent["id"])


# ── Read ──────────────────────────────────────────────────────────────────────

async def test_list_agents(client):
    agent = await _create(client)
    r = await client.get("/api/agents/")
    assert r.status_code == 200
    ids = [a["id"] for a in r.json()]
    assert agent["id"] in ids
    await _delete(client, agent["id"])


async def test_get_agent_by_id(client):
    agent = await _create(client)
    r = await client.get(f"/api/agents/{agent['id']}")
    assert r.status_code == 200
    assert r.json()["id"] == agent["id"]
    await _delete(client, agent["id"])


async def test_get_missing_agent_returns_404(client):
    r = await client.get("/api/agents/nonexistent-id")
    assert r.status_code == 404


# ── Update ────────────────────────────────────────────────────────────────────

async def test_update_agent_name(client):
    agent = await _create(client)
    r = await client.put(f"/api/agents/{agent['id']}", json={"name": "Renamed"})
    assert r.status_code == 200
    assert r.json()["name"] == "Renamed"
    await _delete(client, agent["id"])


async def test_update_agent_tools(client):
    agent = await _create(client)
    r = await client.put(f"/api/agents/{agent['id']}", json={"tools": ["web_search"]})
    assert r.status_code == 200
    assert "web_search" in r.json()["tools"]
    await _delete(client, agent["id"])


# ── Delete ────────────────────────────────────────────────────────────────────

async def test_delete_agent(client):
    agent = await _create(client)
    r = await client.delete(f"/api/agents/{agent['id']}")
    assert r.status_code == 204


async def test_delete_agent_is_gone(client):
    agent = await _create(client)
    await _delete(client, agent["id"])
    r = await client.get(f"/api/agents/{agent['id']}")
    assert r.status_code == 404
