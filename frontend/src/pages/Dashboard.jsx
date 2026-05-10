import { useState, useEffect } from "react";
import { agentsApi } from "../api/agents";
import { workflowsApi } from "../api/workflows";
import { runsApi } from "../api/runs";

function Stat({ label, value, color }) {
  return (
    <div className="card" style={{ textAlign: "center" }}>
      <div style={{ fontSize: 32, fontWeight: 700, color: color || "#7c6af7", marginBottom: 4 }}>{value}</div>
      <div style={{ fontSize: 13, color: "#64748b" }}>{label}</div>
    </div>
  );
}

export default function Dashboard() {
  const [stats, setStats] = useState(null);

  useEffect(() => {
    async function load() {
      const [agents, workflows, runs] = await Promise.all([
        agentsApi.list(),
        workflowsApi.list(),
        runsApi.list(),
      ]);
      const completed = runs.filter((r) => r.status === "completed").length;
      const failed = runs.filter((r) => r.status === "failed").length;
      const totalTokens = runs.reduce((sum, r) => sum + (r.total_tokens || 0), 0);
      setStats({ agents: agents.length, workflows: workflows.length, runs: runs.length, completed, failed, totalTokens });
    }
    load();
  }, []);

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Dashboard</h1>
      </div>

      {stats && (
        <>
          <div className="grid" style={{ gridTemplateColumns: "repeat(3, 1fr)", marginBottom: 24 }}>
            <Stat label="Agents" value={stats.agents} color="#7c6af7" />
            <Stat label="Workflows" value={stats.workflows} color="#4ade80" />
            <Stat label="Total Runs" value={stats.runs} color="#facc15" />
          </div>
          <div className="grid" style={{ gridTemplateColumns: "repeat(3, 1fr)" }}>
            <Stat label="Completed" value={stats.completed} color="#4ade80" />
            <Stat label="Failed" value={stats.failed} color="#f87171" />
            <Stat label="Tokens Used" value={stats.totalTokens.toLocaleString()} color="#94a3b8" />
          </div>
        </>
      )}

      {!stats && <p style={{ color: "#475569" }}>Loading…</p>}
    </div>
  );
}
