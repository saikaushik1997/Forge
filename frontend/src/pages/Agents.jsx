import { useState, useEffect } from "react";
import { agentsApi } from "../api/agents";

const TOOLS = ["web_search", "calculator", "datetime"];
const MODELS = ["claude-sonnet-4-6", "claude-haiku-4-5-20251001", "claude-opus-4-7"];
const CHANNELS = ["", "telegram"];

const CHANNEL_FIELDS = {
  telegram: [
    { key: "bot_token", label: "Bot Token", placeholder: "Token from @BotFather" },
  ],
};

const defaultForm = {
  name: "",
  role: "",
  system_prompt: "",
  model: "claude-sonnet-4-6",
  tools: [],
  memory_enabled: false,
  guardrails: { max_tokens: 2000, max_tool_calls: 5, banned_phrases: "", prompt_injection_detection: false },
  channel_configs: {},
};

export default function Agents() {
  const [agents, setAgents] = useState([]);
  const [showModal, setShowModal] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(defaultForm);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    load();
  }, []);

  async function load() {
    try {
      setAgents(await agentsApi.list());
    } catch (e) {
      console.error(e);
    }
  }

  function openCreate() {
    setEditing(null);
    setForm(defaultForm);
    setShowModal(true);
  }

  function openEdit(agent) {
    setEditing(agent.id);
    // Rebuild channel_configs from masked response — preserve enabled flags, clear tokens
    const configs = {};
    for (const [ch, cfg] of Object.entries(agent.channel_configs || {})) {
      configs[ch] = { enabled: cfg.enabled || false };
      // Don't pre-fill tokens — user must re-enter to change
    }
    setForm({
      name: agent.name,
      role: agent.role,
      system_prompt: agent.system_prompt,
      model: agent.model,
      tools: agent.tools,
      memory_enabled: agent.memory_enabled,
      guardrails: {
        ...agent.guardrails,
        banned_phrases: (agent.guardrails?.banned_phrases || []).join(", "),
      },
      channel_configs: configs,
    });
    setShowModal(true);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    try {
      const payload = {
        ...form,
        guardrails: {
          ...form.guardrails,
          banned_phrases: form.guardrails.banned_phrases
            ? form.guardrails.banned_phrases.split(",").map((s) => s.trim()).filter(Boolean)
            : [],
        },
      };
      if (editing) {
        await agentsApi.update(editing, payload);
      } else {
        await agentsApi.create(payload);
      }
      const hasChannel = Object.values(form.channel_configs || {}).some(c => c.enabled);
      if (hasChannel) {
        await fetch("/api/bots/reload", { method: "POST" });
      }
      setShowModal(false);
      await load();
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  async function handleDelete(id) {
    if (!confirm("Delete this agent?")) return;
    await agentsApi.delete(id);
    await load();
  }

  function toggleTool(tool) {
    setForm((f) => ({
      ...f,
      tools: f.tools.includes(tool) ? f.tools.filter((t) => t !== tool) : [...f.tools, tool],
    }));
  }

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Agents</h1>
        <button className="btn btn-primary" onClick={openCreate}>+ New Agent</button>
      </div>

      {agents.length === 0 ? (
        <div className="empty-state">
          <h3>No agents yet</h3>
          <p>Create your first agent to get started.</p>
        </div>
      ) : (
        <div className="grid">
          {agents.map((agent) => (
            <div className="card" key={agent.id}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
                <strong style={{ fontSize: 16 }}>{agent.name}</strong>
                {agent.channel && <span className="badge badge-green">{agent.channel}</span>}
              </div>
              <p style={{ color: "#94a3b8", fontSize: 13, marginBottom: 12 }}>{agent.role}</p>
              <p style={{ fontSize: 13, color: "#64748b", marginBottom: 16, lineHeight: 1.5 }}>
                {agent.system_prompt.slice(0, 100)}{agent.system_prompt.length > 100 ? "…" : ""}
              </p>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 16 }}>
                <span className="badge badge-purple">{agent.model.split("-").slice(1, 3).join("-")}</span>
                {agent.tools.map((t) => <span key={t} className="badge badge-yellow">{t}</span>)}
                {agent.memory_enabled && <span className="badge badge-green">memory</span>}
                {Object.entries(agent.channel_configs || {}).filter(([, c]) => c.enabled).map(([ch]) => (
                  <span key={ch} className="badge badge-green">✈ {ch}</span>
                ))}
              </div>
              <div style={{ display: "flex", gap: 8 }}>
                <button className="btn btn-ghost" style={{ flex: 1 }} onClick={() => openEdit(agent)}>Edit</button>
                <button className="btn btn-danger" onClick={() => handleDelete(agent.id)}>Delete</button>
              </div>
            </div>
          ))}
        </div>
      )}

      {showModal && (
        <div className="modal-backdrop" onClick={() => setShowModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>{editing ? "Edit Agent" : "New Agent"}</h2>
            <form onSubmit={handleSubmit}>
              <div className="form-row">
                <div className="form-group">
                  <label>Name</label>
                  <input required value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} placeholder="Research Bot" />
                </div>
                <div className="form-group">
                  <label>Role</label>
                  <input required value={form.role} onChange={(e) => setForm((f) => ({ ...f, role: e.target.value }))} placeholder="Researcher" />
                </div>
              </div>
              <div className="form-group">
                <label>System Prompt</label>
                <textarea required value={form.system_prompt} onChange={(e) => setForm((f) => ({ ...f, system_prompt: e.target.value }))} placeholder="You are a research assistant..." rows={4} />
              </div>
              <div className="form-group">
                <label>Model</label>
                <select value={form.model} onChange={(e) => setForm((f) => ({ ...f, model: e.target.value }))}>
                  {MODELS.map((m) => <option key={m} value={m}>{m}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label>Tools</label>
                <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
                  {TOOLS.map((tool) => (
                    <label key={tool} style={{ display: "flex", alignItems: "center", gap: 6, cursor: "pointer", fontSize: 13 }}>
                      <input type="checkbox" checked={form.tools.includes(tool)} onChange={() => toggleTool(tool)} />
                      {tool}
                    </label>
                  ))}
                </div>
              </div>
              <div className="form-group">
                <label>Options</label>
                <div style={{ display: "flex", gap: 20, justifyContent: "center" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 6, cursor: "pointer", fontSize: 13 }}
                    onClick={() => setForm((f) => ({ ...f, memory_enabled: !f.memory_enabled }))}>
                    <input type="checkbox" checked={form.memory_enabled} onChange={() => {}} />
                    <span>Enable Memory</span>
                  </div>
                  {Object.keys(CHANNEL_FIELDS).map((channel) => (
                    <div key={channel} style={{ display: "flex", alignItems: "center", gap: 6, cursor: "pointer", fontSize: 13 }}
                      onClick={() => setForm((f) => ({
                        ...f,
                        channel_configs: {
                          ...f.channel_configs,
                          [channel]: { ...(f.channel_configs?.[channel] || {}), enabled: !f.channel_configs?.[channel]?.enabled },
                        },
                      }))}>
                      <input type="checkbox" checked={form.channel_configs?.[channel]?.enabled || false} onChange={() => {}} />
                      <span>Enable {channel.charAt(0).toUpperCase() + channel.slice(1)}</span>
                    </div>
                  ))}
                </div>
                {Object.entries(CHANNEL_FIELDS).map(([channel, fields]) =>
                  form.channel_configs?.[channel]?.enabled && (
                    <div key={channel} style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 8 }}>
                      {fields.map((field) => (
                        <input
                          key={field.key}
                          type="password"
                          placeholder={editing ? `${field.label} — leave blank to keep existing` : field.placeholder}
                          value={form.channel_configs?.[channel]?.[field.key] || ""}
                          onChange={(e) => setForm((f) => ({
                            ...f,
                            channel_configs: {
                              ...f.channel_configs,
                              [channel]: { ...(f.channel_configs?.[channel] || {}), [field.key]: e.target.value },
                            },
                          }))}
                        />
                      ))}
                    </div>
                  )
                )}
              </div>
              <div className="form-group">
                <label>Guardrails</label>
                <div style={{ display: "flex", gap: 12, marginBottom: 10 }}>
                  <div style={{ flex: 1 }}>
                    <label style={{ fontSize: 12, color: "#64748b" }}>Max Tokens</label>
                    <input
                      type="number"
                      value={form.guardrails.max_tokens || 2000}
                      onChange={(e) => setForm((f) => ({ ...f, guardrails: { ...f.guardrails, max_tokens: parseInt(e.target.value) } }))}
                    />
                  </div>
                  <div style={{ flex: 1 }}>
                    <label style={{ fontSize: 12, color: "#64748b" }}>Max Tool Calls</label>
                    <input
                      type="number"
                      min={1}
                      max={20}
                      value={form.guardrails.max_tool_calls ?? 5}
                      onChange={(e) => setForm((f) => ({ ...f, guardrails: { ...f.guardrails, max_tool_calls: parseInt(e.target.value) } }))}
                    />
                  </div>
                </div>
                <div style={{ marginBottom: 10 }}>
                  <label style={{ fontSize: 12, color: "#64748b" }}>Banned Phrases <span style={{ color: "#475569" }}>(comma-separated — redacted from output)</span></label>
                  <input
                    type="text"
                    placeholder="e.g. password, SSN, confidential"
                    value={form.guardrails.banned_phrases || ""}
                    onChange={(e) => setForm((f) => ({ ...f, guardrails: { ...f.guardrails, banned_phrases: e.target.value } }))}
                  />
                </div>
                <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer", fontSize: 13 }}
                  onClick={() => setForm((f) => ({ ...f, guardrails: { ...f.guardrails, prompt_injection_detection: !f.guardrails.prompt_injection_detection } }))}>
                  <input type="checkbox" checked={form.guardrails.prompt_injection_detection || false} onChange={() => {}} />
                  Prompt injection detection
                </label>
              </div>
              <div className="modal-actions">
                <button type="button" className="btn btn-ghost" onClick={() => setShowModal(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={loading}>
                  {loading ? "Saving…" : editing ? "Save Changes" : "Create Agent"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
