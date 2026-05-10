import client from "./client";

export const workflowsApi = {
  list: () => client.get("/api/workflows/").then((r) => r.data),
  get: (id) => client.get(`/api/workflows/${id}`).then((r) => r.data),
  create: (data) => client.post("/api/workflows/", data).then((r) => r.data),
  update: (id, data) => client.put(`/api/workflows/${id}`, data).then((r) => r.data),
  delete: (id) => client.delete(`/api/workflows/${id}`),
};
