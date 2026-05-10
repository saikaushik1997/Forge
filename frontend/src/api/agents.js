import client from "./client";

export const agentsApi = {
  list: () => client.get("/api/agents/").then((r) => r.data),
  get: (id) => client.get(`/api/agents/${id}`).then((r) => r.data),
  create: (data) => client.post("/api/agents/", data).then((r) => r.data),
  update: (id, data) => client.put(`/api/agents/${id}`, data).then((r) => r.data),
  delete: (id) => client.delete(`/api/agents/${id}`),
};
