"""
Integration tests — require a running PostgreSQL and Anthropic API key.
These tests create real agents, workflows, and runs, then clean up after themselves.
"""
import asyncio
import pytest


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _create_agent(client, **kwargs) -> dict:
    payload = {
        "name": "Exec Test Agent",
        "role": "Tester",
        "system_prompt": "You are a test agent. Reply with exactly one word: OK.",
        "model": "claude-sonnet-4-6",
        "tools": [],
        "guardrails": {"max_tokens": 10},
        **kwargs,
    }
    r = await client.post("/api/agents/", json=payload)
    assert r.status_code == 201
    return r.json()


async def _create_workflow(client, agent_id: str) -> dict:
    r = await client.post("/api/workflows/", json={
        "name": "Exec Test Workflow",
        "description": "Created by integration test",
        "graph_definition": {
            "nodes": [{"id": "node_0", "type": "agentNode", "position": {"x": 0, "y": 0}, "data": {"agent_id": agent_id, "label": "Exec Test Agent"}}],
            "edges": [],
        },
    })
    assert r.status_code == 201
    return r.json()


async def _poll_run(client, run_id: str, timeout: int = 60) -> dict:
    for _ in range(timeout):
        r = await client.get(f"/api/runs/{run_id}")
        assert r.status_code == 200
        run = r.json()
        if run["status"] in ("completed", "failed"):
            return run
        await asyncio.sleep(1)
    pytest.fail(f"Run {run_id} did not complete within {timeout}s")


async def _cleanup(client, agent_id: str, workflow_id: str):
    await client.delete(f"/api/workflows/{workflow_id}")
    await client.delete(f"/api/agents/{agent_id}")


# ── Workflow execution ────────────────────────────────────────────────────────

async def test_run_completes(client):
    agent = await _create_agent(client)
    workflow = await _create_workflow(client, agent["id"])

    r = await client.post("/api/runs", json={"workflow_id": workflow["id"], "input": "ping"})
    assert r.status_code == 201
    run_id = r.json()["run_id"]

    run = await _poll_run(client, run_id)
    assert run["status"] == "completed"
    assert run["output"]

    await _cleanup(client, agent["id"], workflow["id"])


async def test_run_has_nonzero_tokens(client):
    agent = await _create_agent(client)
    workflow = await _create_workflow(client, agent["id"])

    r = await client.post("/api/runs", json={"workflow_id": workflow["id"], "input": "ping"})
    run_id = r.json()["run_id"]

    run = await _poll_run(client, run_id)
    assert run["total_tokens"] > 0

    await _cleanup(client, agent["id"], workflow["id"])


# ── Message delivery ──────────────────────────────────────────────────────────

async def test_messages_persisted_after_run(client):
    agent = await _create_agent(client)
    workflow = await _create_workflow(client, agent["id"])

    r = await client.post("/api/runs", json={"workflow_id": workflow["id"], "input": "ping"})
    run_id = r.json()["run_id"]

    await _poll_run(client, run_id)

    r = await client.get(f"/api/runs/{run_id}/messages")
    assert r.status_code == 200
    messages = r.json()
    assert len(messages) > 0

    await _cleanup(client, agent["id"], workflow["id"])


async def test_messages_have_correct_fields(client):
    agent = await _create_agent(client)
    workflow = await _create_workflow(client, agent["id"])

    r = await client.post("/api/runs", json={"workflow_id": workflow["id"], "input": "ping"})
    run_id = r.json()["run_id"]

    await _poll_run(client, run_id)

    messages = (await client.get(f"/api/runs/{run_id}/messages")).json()
    assert len(messages) > 0
    msg = messages[0]
    assert "from_agent" in msg
    assert "to_agent" in msg
    assert "content" in msg
    assert msg["content"]  # non-empty

    await _cleanup(client, agent["id"], workflow["id"])


async def test_failed_workflow_not_found_agent(client):
    r = await client.post("/api/runs", json={"workflow_id": "nonexistent-id", "input": "ping"})
    assert r.status_code == 404
