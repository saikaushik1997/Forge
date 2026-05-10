import { useState, useEffect, useRef } from "react";
import { workflowsApi } from "../api/workflows";
import { agentsApi } from "../api/agents";
import WorkflowCanvas from "../components/WorkflowCanvas";

export default function Workflows() {
  const [workflows, setWorkflows] = useState([]);
  const [agents, setAgents] = useState([]);
  const [editing, setEditing] = useState(null); // workflow being edited in canvas
  const [showNewModal, setShowNewModal] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const graphRef = useRef({ nodes: [], edges: [] });

  useEffect(() => {
    load();
  }, []);

  async function load() {
    const [wfs, ags] = await Promise.all([workflowsApi.list(), agentsApi.list()]);
    setWorkflows(wfs);
    setAgents(ags);
  }

  async function createWorkflow(e) {
    e.preventDefault();
    await workflowsApi.create({ name: newName, description: newDesc });
    setShowNewModal(false);
    setNewName("");
    setNewDesc("");
    await load();
  }

  async function openCanvas(workflow) {
    graphRef.current = workflow.graph_definition;
    setEditing(workflow);
  }

  async function saveCanvas() {
    await workflowsApi.update(editing.id, {
      name: editing.name,
      description: editing.description,
      graph_definition: graphRef.current,
    });
    setEditing(null);
    await load();
  }

  async function deleteWorkflow(id) {
    if (!confirm("Delete this workflow?")) return;
    await workflowsApi.delete(id);
    await load();
  }

  if (editing) {
    return (
      <div style={{ display: "flex", flexDirection: "column", height: "calc(100vh - 64px)" }}>
        <div className="page-header" style={{ marginBottom: 16 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <button className="btn btn-ghost" onClick={() => setEditing(null)}>← Back</button>
            <h1 className="page-title">{editing.name}</h1>
          </div>
          <button className="btn btn-primary" onClick={saveCanvas}>Save Workflow</button>
        </div>

        <div style={{ display: "flex", gap: 16, flex: 1, minHeight: 0 }}>
          {/* Agent sidebar */}
          <div className="card" style={{ width: 200, flexShrink: 0, overflowY: "auto" }}>
            <p style={{ fontSize: 12, color: "#64748b", marginBottom: 12 }}>DRAG AGENTS ONTO CANVAS</p>
            {agents.map((agent) => (
              <div
                key={agent.id}
                draggable
                onDragStart={(e) =>
                  e.dataTransfer.setData("application/forge-agent", JSON.stringify(agent))
                }
                style={{
                  padding: "8px 12px",
                  background: "#0f1117",
                  border: "1px solid #2d3148",
                  borderRadius: 8,
                  marginBottom: 8,
                  cursor: "grab",
                  fontSize: 13,
                }}
              >
                <div style={{ fontWeight: 500 }}>{agent.name}</div>
                <div style={{ color: "#64748b", fontSize: 11 }}>{agent.role}</div>
              </div>
            ))}
            {agents.length === 0 && (
              <p style={{ color: "#475569", fontSize: 12 }}>No agents yet. Create some first.</p>
            )}
          </div>

          {/* Canvas */}
          <div className="card" style={{ flex: 1, padding: 0, overflow: "hidden" }}>
            <WorkflowCanvas
              initialNodes={editing.graph_definition?.nodes || []}
              initialEdges={editing.graph_definition?.edges || []}
              onChange={(graph) => { graphRef.current = graph; }}
            />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Workflows</h1>
        <button className="btn btn-primary" onClick={() => setShowNewModal(true)}>+ New Workflow</button>
      </div>

      {workflows.length === 0 ? (
        <div className="empty-state">
          <h3>No workflows yet</h3>
          <p>Create a workflow to connect agents into a pipeline.</p>
        </div>
      ) : (
        <div className="grid">
          {workflows.map((wf) => (
            <div className="card" key={wf.id}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
                <strong style={{ fontSize: 16 }}>{wf.name}</strong>
                {wf.is_template && <span className="badge badge-purple">template</span>}
              </div>
              <p style={{ color: "#64748b", fontSize: 13, marginBottom: 12 }}>{wf.description || "No description"}</p>
              <p style={{ color: "#475569", fontSize: 12, marginBottom: 16 }}>
                {wf.graph_definition?.nodes?.length || 0} agents · {wf.graph_definition?.edges?.length || 0} connections
              </p>
              <div style={{ display: "flex", gap: 8 }}>
                <button className="btn btn-ghost" style={{ flex: 1 }} onClick={() => openCanvas(wf)}>Open Canvas</button>
                <button className="btn btn-danger" onClick={() => deleteWorkflow(wf.id)}>Delete</button>
              </div>
            </div>
          ))}
        </div>
      )}

      {showNewModal && (
        <div className="modal-backdrop" onClick={() => setShowNewModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>New Workflow</h2>
            <form onSubmit={createWorkflow}>
              <div className="form-group">
                <label>Name</label>
                <input required value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="Research & Summarize" />
              </div>
              <div className="form-group">
                <label>Description</label>
                <textarea value={newDesc} onChange={(e) => setNewDesc(e.target.value)} placeholder="What does this workflow do?" rows={3} />
              </div>
              <div className="modal-actions">
                <button type="button" className="btn btn-ghost" onClick={() => setShowNewModal(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary">Create</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
