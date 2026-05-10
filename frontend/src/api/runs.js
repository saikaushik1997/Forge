import client from "./client";

export const runsApi = {
  create: (workflow_id, input) => client.post("/api/runs", { workflow_id, input }).then((r) => r.data),
  get: (id) => client.get(`/api/runs/${id}`).then((r) => r.data),
  list: () => client.get("/api/runs").then((r) => r.data),
  messages: (id) => client.get(`/api/runs/${id}/messages`).then((r) => r.data),
};

export function connectRunSocket(runId, onEvent) {
  const wsUrl = `ws://localhost:8001/api/ws/runs/${runId}`;
  const ws = new WebSocket(wsUrl);
  ws.onmessage = (e) => onEvent(JSON.parse(e.data));
  ws.onerror = (e) => console.error("WS error", e);
  return ws;
}
