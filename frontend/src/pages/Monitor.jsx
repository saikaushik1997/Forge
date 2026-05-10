import { useState, useEffect, useRef } from "react";
import { runsApi } from "../api/runs";
import { workflowsApi } from "../api/workflows";

const STATUS_COLOR = { running: "#facc15", completed: "#4ade80", failed: "#f87171" };

function timeAgo(iso) {
  const s = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  return `${Math.floor(m / 60)}h ago`;
}

export default function Monitor() {
  const [runs, setRuns] = useState([]);
  const [wfNames, setWfNames] = useState({});
  const [selected, setSelected] = useState(null);
  const [messages, setMessages] = useState([]);
  const pollRef = useRef(null);

  useEffect(() => {
    loadAll();
    pollRef.current = setInterval(loadAll, 5000);
    return () => clearInterval(pollRef.current);
  }, []);

  async function loadAll() {
    const [runList, wfList] = await Promise.all([runsApi.list(), workflowsApi.list()]);
    setRuns(runList);
    setWfNames(Object.fromEntries(wfList.map((w) => [w.id, w.name])));
  }

  async function selectRun(run) {
    setSelected(run);
    setMessages(await runsApi.messages(run.id));
  }

  // Refresh selected run while it's still running
  useEffect(() => {
    if (!selected || selected.status !== "running") return;
    const t = setInterval(async () => {
      const [updated, msgs] = await Promise.all([
        runsApi.get(selected.id),
        runsApi.messages(selected.id),
      ]);
      setSelected(updated);
      setMessages(msgs);
    }, 2000);
    return () => clearInterval(t);
  }, [selected?.id, selected?.status]);

  return (
    <div style={{ display: "flex", gap: 16, height: "calc(100vh - 64px)" }}>
      {/* ── Run list ── */}
      <div className="card" style={{ width: 300, flexShrink: 0, overflowY: "auto", padding: 0 }}>
        <div style={{ padding: "14px 16px 10px", borderBottom: "1px solid #1e2235" }}>
          <p style={{ fontSize: 11, color: "#64748b", margin: 0, letterSpacing: "0.06em" }}>RECENT RUNS</p>
        </div>

        {runs.length === 0 && (
          <p style={{ color: "#475569", fontSize: 13, padding: 16 }}>No runs yet.</p>
        )}

        {runs.map((run) => (
          <div
            key={run.id}
            onClick={() => selectRun(run)}
            style={{
              padding: "12px 16px",
              borderBottom: "1px solid #1e2235",
              cursor: "pointer",
              background: selected?.id === run.id ? "#1a1d2e" : "transparent",
              transition: "background 0.1s",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
              <span
                style={{
                  width: 7,
                  height: 7,
                  borderRadius: "50%",
                  background: STATUS_COLOR[run.status] || "#64748b",
                  flexShrink: 0,
                  boxShadow: run.status === "running" ? `0 0 6px ${STATUS_COLOR.running}` : "none",
                }}
              />
              <span style={{ fontSize: 13, fontWeight: 500, flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {wfNames[run.workflow_id] || "Workflow"}
              </span>
              <span style={{ fontSize: 11, color: "#64748b", flexShrink: 0 }}>{timeAgo(run.started_at)}</span>
            </div>
            <div style={{ fontSize: 12, color: "#64748b", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", paddingLeft: 15 }}>
              {run.input}
            </div>
            {run.total_tokens > 0 && (
              <div style={{ fontSize: 11, color: "#475569", paddingLeft: 15, marginTop: 2 }}>
                {run.total_tokens.toLocaleString()} tokens
              </div>
            )}
          </div>
        ))}
      </div>

      {/* ── Run detail ── */}
      <div className="card" style={{ flex: 1, overflowY: "auto" }}>
        {!selected ? (
          <div style={{ color: "#475569", textAlign: "center", paddingTop: 80, fontSize: 14 }}>
            Select a run to inspect
          </div>
        ) : (
          <>
            {/* Header */}
            <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 24 }}>
              <h2 style={{ margin: 0, fontSize: 18 }}>{wfNames[selected.workflow_id] || "Run"}</h2>
              <span
                style={{
                  padding: "2px 10px",
                  borderRadius: 12,
                  fontSize: 12,
                  fontWeight: 600,
                  background: (STATUS_COLOR[selected.status] || "#64748b") + "22",
                  color: STATUS_COLOR[selected.status] || "#64748b",
                }}
              >
                {selected.status}
              </span>
              {selected.total_tokens > 0 && (
                <span style={{ fontSize: 12, color: "#64748b", marginLeft: "auto" }}>
                  {selected.total_tokens.toLocaleString()} tokens
                </span>
              )}
            </div>

            {/* Input */}
            <Section label="INPUT">
              <div style={{ background: "#0f1117", borderRadius: 8, padding: 12, fontSize: 13, color: "#e2e8f0" }}>
                {selected.input}
              </div>
            </Section>

            {/* Message thread */}
            {messages.length > 0 && (
              <Section label="AGENT MESSAGES">
                <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                  {messages.map((msg) => (
                    <div key={msg.id} style={{ background: "#0f1117", borderRadius: 8, padding: 14 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                        <span style={{ fontSize: 11, color: "#7c6af7", fontWeight: 700 }}>{msg.from_agent}</span>
                        <span style={{ fontSize: 11, color: "#475569" }}>→</span>
                        <span style={{ fontSize: 11, color: "#4ade80", fontWeight: 700 }}>{msg.to_agent}</span>
                        <span style={{ fontSize: 11, color: "#475569", marginLeft: "auto" }}>
                          {new Date(msg.timestamp).toLocaleTimeString()}
                        </span>
                      </div>
                      <div style={{ fontSize: 13, color: "#cbd5e1", lineHeight: 1.7, whiteSpace: "pre-wrap" }}>
                        {msg.content}
                      </div>
                    </div>
                  ))}
                </div>
              </Section>
            )}

            {/* Final output */}
            {selected.output && (
              <Section label="FINAL OUTPUT">
                <div style={{ background: "#0f1117", borderRadius: 8, padding: 12, fontSize: 13, color: "#e2e8f0", lineHeight: 1.7, whiteSpace: "pre-wrap" }}>
                  {selected.output}
                </div>
              </Section>
            )}

            {selected.status === "running" && (
              <div style={{ color: "#facc15", fontSize: 13, marginTop: 12 }}>⏳ Run in progress…</div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function Section({ label, children }) {
  return (
    <div style={{ marginBottom: 24 }}>
      <p style={{ fontSize: 11, color: "#64748b", marginBottom: 8, letterSpacing: "0.06em" }}>{label}</p>
      {children}
    </div>
  );
}
