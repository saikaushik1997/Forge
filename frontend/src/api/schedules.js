import client from "./client";

export const schedulesApi = {
  list: (workflowId) =>
    client.get("/api/schedules/", { params: { workflow_id: workflowId } }).then((r) => r.data),
  create: (data) => client.post("/api/schedules/", data).then((r) => r.data),
  update: (id, data) => client.put(`/api/schedules/${id}`, data).then((r) => r.data),
  delete: (id) => client.delete(`/api/schedules/${id}`),
};
