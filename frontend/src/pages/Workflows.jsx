import { useState, useEffect, useRef } from "react";
import { workflowsApi } from "../api/workflows";
import { agentsApi } from "../api/agents";
import { runsApi, connectRunSocket } from "../api/runs";
import { schedulesApi } from "../api/schedules";
import WorkflowCanvas from "../components/WorkflowCanvas";

export default function Workflows() {
  const [workflows, setWorkflows] = useState([]);
  const [agents, setAgents] = useState([]);
  const [editing, setEditing] = useState(null); // workflow being edited in canvas
  const [showNewModal, setShowNewModal] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const graphRef = useRef({ nodes: [], edges: [] });
  const [runModal, setRunModal] = useState(null); // workflow to run
  const [runInput, setRunInput] = useState("");
  const [runEvents, setRunEvents] = useState([]);
  const [running, setRunning] = useState(false);
  const [cloneModal, setCloneModal] = useState(null);
  const [cloneName, setCloneName] = useState("");
  const [scheduleModal, setScheduleModal] = useState(null); // workflow
  const [schedules, setSchedules] = useState([]);
  const [newCron, setNewCron] = useState("0 9 * * *");
  const [newScheduleInput, setNewScheduleInput] = useState("");

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

  async function useTemplate(e) {
    e.preventDefault();
    await workflowsApi.create({
      name: cloneName,
      description: cloneModal.description,
      graph_definition: cloneModal.graph_definition,
      is_template: false,
    });
    setCloneModal(null);
    setCloneName("");
    await load();
  }

  async function toggleTelegram(wf) {
    await workflowsApi.update(wf.id, { telegram_enabled: !wf.telegram_enabled });
    await load();
  }

  async function openScheduleModal(wf) {
    const list = await schedulesApi.list(wf.id);
    setSchedules(list);
    setNewCron("0 9 * * *");
    setNewScheduleInput("");
    setScheduleModal(wf);
  }

  async function createSchedule(e) {
    e.preventDefault();
    await schedulesApi.create({ workflow_id: scheduleModal.id, cron_expression: newCron, input: newScheduleInput });
    const list = await schedulesApi.list(scheduleModal.id);
    setSchedules(list);
    setNewCron("0 9 * * *");
    setNewScheduleInput("");
  }

  async function toggleSchedule(s) {
    await schedulesApi.update(s.id, { enabled: !s.enabled });
    const list = await schedulesApi.list(scheduleModal.id);
    setSchedules(list);
  }

  async function deleteSchedule(s) {
    await schedulesApi.delete(s.id);
    const list = await schedulesApi.list(scheduleModal.id);
    setSchedules(list);
  }

  async function startRun(e) {
    e.preventDefault();
    setRunning(true);
    setRunEvents([]);
    try {
      const { run_id } = await runsApi.create(runModal.id, runInput);
      const ws = connectRunSocket(run_id, (event) => {
        setRunEvents((prev) => [...prev, event]);
        if (event.type === "run_complete" || event.type === "run_failed") {
          setRunning(false);
          ws.close();
        }
      });
    } catch (e) {
      setRunEvents([{ type: "run_failed", error: e.message }]);
      setRunning(false);
    }
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

      {workflows.some((wf) => wf.is_template) && (
        <>
          <h2 style={{ fontSize: 14, color: "#64748b", letterSpacing: "0.06em", marginBottom: 12 }}>TEMPLATES</h2>
          <div className="grid" style={{ marginBottom: 32 }}>
            {workflows.filter((wf) => wf.is_template).map((wf) => (
              <div className="card" key={wf.id} style={{ borderColor: "#7c6af733" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
                  <strong style={{ fontSize: 16 }}>{wf.name}</strong>
                  <span className="badge badge-purple">template</span>
                </div>
                <p style={{ color: "#64748b", fontSize: 13, marginBottom: 16 }}>{wf.description || "No description"}</p>
                <p style={{ color: "#475569", fontSize: 12, marginBottom: 16 }}>
                  {wf.graph_definition?.nodes?.length || 0} agents · {wf.graph_definition?.edges?.length || 0} connections
                </p>
                <button
                  className="btn btn-primary"
                  style={{ width: "100%" }}
                  onClick={() => { setCloneModal(wf); setCloneName(wf.name); }}
                >Use Template</button>
              </div>
            ))}
          </div>
          <h2 style={{ fontSize: 14, color: "#64748b", letterSpacing: "0.06em", marginBottom: 12 }}>MY WORKFLOWS</h2>
        </>
      )}

      {workflows.filter((wf) => !wf.is_template).length === 0 ? (
        <div className="empty-state">
          <h3>No workflows yet</h3>
          <p>Create a workflow or use a template above.</p>
        </div>
      ) : (
        <div className="grid">
          {workflows.filter((wf) => !wf.is_template).map((wf) => (
            <div className="card" key={wf.id}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
                <strong style={{ fontSize: 16 }}>{wf.name}</strong>
                <div style={{ display: "flex", gap: 6 }}>
                  {wf.is_template && <span className="badge badge-purple">template</span>}
                  {wf.telegram_enabled && <span className="badge badge-green">✈ telegram</span>}
                </div>
              </div>
              <p style={{ color: "#64748b", fontSize: 13, marginBottom: 12 }}>{wf.description || "No description"}</p>
              <p style={{ color: "#475569", fontSize: 12, marginBottom: 16 }}>
                {wf.graph_definition?.nodes?.length || 0} agents · {wf.graph_definition?.edges?.length || 0} connections
              </p>
              <div style={{ display: "flex", gap: 8 }}>
                <button className="btn btn-ghost" style={{ flex: 1 }} onClick={() => openCanvas(wf)}>Canvas</button>
                <button className="btn btn-primary" style={{ flex: 1 }} onClick={() => { setRunModal(wf); setRunInput(""); setRunEvents([]); }}>▶ Run</button>
                <button
                  className="btn btn-ghost"
                  title="Schedule"
                  onClick={() => openScheduleModal(wf)}
                >⏰</button>
                <button className="btn btn-danger" onClick={() => deleteWorkflow(wf.id)}>Del</button>
              </div>
            </div>
          ))}
        </div>
      )}

      {runModal && (
        <div className="modal-backdrop" onClick={() => !running && setRunModal(null)}>
          <div className="modal" style={{ width: 600 }} onClick={(e) => e.stopPropagation()}>
            <h2>▶ Run — {runModal.name}</h2>
            <form onSubmit={startRun}>
              <div className="form-group">
                <label>Input</label>
                <textarea required rows={3} value={runInput} onChange={(e) => setRunInput(e.target.value)} placeholder="What should the agents work on?" disabled={running} />
              </div>
              {runEvents.length === 0 && !running && (
                <div className="modal-actions">
                  <button type="button" className="btn btn-ghost" onClick={() => setRunModal(null)}>Cancel</button>
                  <button type="submit" className="btn btn-primary">Run Workflow</button>
                </div>
              )}
            </form>

            {(running || runEvents.length > 0) && (
              <div style={{ marginTop: 16 }}>
                <p style={{ fontSize: 12, color: "#64748b", marginBottom: 8 }}>LIVE EVENTS</p>
                <div style={{ background: "#0f1117", borderRadius: 8, padding: 12, maxHeight: 300, overflowY: "auto", fontFamily: "monospace", fontSize: 12 }}>
                  {runEvents.map((ev, i) => (
                    <div key={i} style={{ marginBottom: 8, color: ev.type === "run_failed" ? "#f87171" : ev.type === "run_complete" ? "#4ade80" : "#e2e8f0" }}>
                      {ev.type === "node_start" && <span>🔄 <b>{ev.agent}</b> started</span>}
                      {ev.type === "tool_call" && <span style={{ color: "#facc15" }}>🔧 <b>{ev.agent}</b> calling <b>{ev.tool}</b></span>}
                      {ev.type === "node_complete" && (
                        <div>
                          <span>✅ <b>{ev.agent}</b> finished ({ev.tokens} tokens)</span>
                          <div style={{ color: "#94a3b8", marginTop: 4, whiteSpace: "pre-wrap" }}>{ev.output}</div>
                        </div>
                      )}
                      {ev.type === "run_complete" && <span>🎉 Done! Total tokens: {ev.tokens}</span>}
                      {ev.type === "run_failed" && <span>❌ Failed: {ev.error}</span>}
                    </div>
                  ))}
                  {running && <span style={{ color: "#7c6af7" }}>⏳ Running…</span>}
                </div>
                {!running && (
                  <div className="modal-actions">
                    <button className="btn btn-ghost" onClick={() => setRunModal(null)}>Close</button>
                  </div>
                )}
              </div>
            )}
          </div>
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

      {cloneModal && (
        <div className="modal-backdrop" onClick={() => setCloneModal(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>Use Template — {cloneModal.name}</h2>
            <form onSubmit={useTemplate}>
              <div className="form-group">
                <label>Workflow Name</label>
                <input required value={cloneName} onChange={(e) => setCloneName(e.target.value)} placeholder="My Workflow" />
              </div>
              <div className="modal-actions">
                <button type="button" className="btn btn-ghost" onClick={() => setCloneModal(null)}>Cancel</button>
                <button type="submit" className="btn btn-primary">Create</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {scheduleModal && (
        <div className="modal-backdrop" onClick={() => setScheduleModal(null)}>
          <div className="modal" style={{ width: 560 }} onClick={(e) => e.stopPropagation()}>
            <h2>⏰ Schedules — {scheduleModal.name}</h2>

            <form onSubmit={createSchedule} style={{ marginBottom: 24 }}>
              <div className="form-group">
                <label>Cron Expression</label>
                <input
                  required
                  value={newCron}
                  onChange={(e) => setNewCron(e.target.value)}
                  placeholder="0 9 * * *"
                  style={{ fontFamily: "monospace" }}
                />
                <p style={{ fontSize: 11, color: "#64748b", marginTop: 4 }}>
                  Examples: <code>0 9 * * *</code> daily 9am · <code>0 */6 * * *</code> every 6h · <code>*/30 * * * *</code> every 30min
                </p>
              </div>
              <div className="form-group">
                <label>Default Input</label>
                <textarea
                  rows={2}
                  value={newScheduleInput}
                  onChange={(e) => setNewScheduleInput(e.target.value)}
                  placeholder="What should the agents work on when this fires?"
                />
              </div>
              <button type="submit" className="btn btn-primary">Add Schedule</button>
            </form>

            {schedules.length > 0 && (
              <>
                <p style={{ fontSize: 12, color: "#64748b", marginBottom: 8 }}>EXISTING SCHEDULES</p>
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {schedules.map((s) => (
                    <div key={s.id} style={{ background: "#0f1117", border: "1px solid #2d3148", borderRadius: 8, padding: "10px 14px", display: "flex", alignItems: "center", gap: 12 }}>
                      <div style={{ flex: 1 }}>
                        <code style={{ fontSize: 13, color: "#7c6af7" }}>{s.cron_expression}</code>
                        {s.input && <p style={{ fontSize: 12, color: "#64748b", marginTop: 2, marginBottom: 0 }}>{s.input.slice(0, 60)}{s.input.length > 60 ? "…" : ""}</p>}
                        <p style={{ fontSize: 11, color: "#475569", marginTop: 2, marginBottom: 0 }}>
                          Next: {s.next_run_at ? new Date(s.next_run_at).toLocaleString() : "—"}
                        </p>
                      </div>
                      <button
                        className="btn btn-ghost"
                        style={{ fontSize: 12, color: s.enabled ? "#4ade80" : "#64748b" }}
                        onClick={() => toggleSchedule(s)}
                      >{s.enabled ? "On" : "Off"}</button>
                      <button className="btn btn-danger" style={{ fontSize: 12 }} onClick={() => deleteSchedule(s)}>Del</button>
                    </div>
                  ))}
                </div>
              </>
            )}

            <div className="modal-actions" style={{ marginTop: 20 }}>
              <button className="btn btn-ghost" onClick={() => setScheduleModal(null)}>Close</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
