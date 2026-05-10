import { useCallback, useMemo, useRef, useState } from "react";
import ReactFlow, {
  addEdge,
  Background,
  Controls,
  MiniMap,
  MarkerType,
  BaseEdge,
  EdgeLabelRenderer,
  useNodesState,
  useEdgesState,
  Handle,
  Position,
} from "reactflow";
import "reactflow/dist/style.css";

// Curves around the left side — used for back edges (feedback loops)
function FeedbackEdge({ id, sourceX, sourceY, targetX, targetY, label }) {
  const sideX = Math.min(sourceX, targetX) - 180;
  const path = `M ${sourceX} ${sourceY} C ${sideX} ${sourceY} ${sideX} ${targetY} ${targetX} ${targetY}`;
  const labelX = sideX - 8;
  const labelY = (sourceY + targetY) / 2;
  const color = "#f59e0b";

  return (
    <>
      <BaseEdge
        id={id}
        path={path}
        style={{ stroke: color, strokeWidth: 2, strokeDasharray: "6 3" }}
        markerEnd={`url(#feedback-arrow)`}
      />
      {/* inline arrowhead definition since we use a fixed color */}
      <defs>
        <marker id="feedback-arrow" markerWidth="10" markerHeight="10" refX="6" refY="3" orient="auto">
          <path d="M0,0 L0,6 L9,3 z" fill={color} />
        </marker>
      </defs>
      <EdgeLabelRenderer>
        <div style={{
          position: "absolute",
          transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
          background: "#1a1d2e",
          border: `1px solid ${color}`,
          padding: "2px 7px",
          borderRadius: 4,
          fontSize: 11,
          fontWeight: 600,
          color,
          pointerEvents: "all",
          whiteSpace: "nowrap",
        }}>
          {label || "↩ loop"}
        </div>
      </EdgeLabelRenderer>
    </>
  );
}

function AgentNode({ data }) {
  const isStart = data.isStart;
  const isEnd = data.isEnd;

  return (
    <div style={{
      background: "#1a1d2e",
      border: `2px solid ${isStart ? "#4ade80" : isEnd ? "#f87171" : "#7c6af7"}`,
      borderRadius: 10,
      padding: "10px 16px",
      color: "#e2e8f0",
      fontSize: 13,
      minWidth: 140,
      position: "relative",
    }}>
      <Handle
        type="target"
        position={Position.Top}
        style={{ background: "#7c6af7", opacity: isStart ? 0.2 : 1 }}
      />

      {/* role badge top-right */}
      <div style={{
        position: "absolute",
        top: 6,
        right: 8,
        fontSize: 9,
        fontWeight: 700,
        letterSpacing: "0.05em",
        color: isStart ? "#4ade80" : isEnd ? "#f87171" : "#7c6af7",
        textTransform: "uppercase",
      }}>
        {isStart ? "start" : isEnd ? "end" : ""}
      </div>

      <div style={{ fontWeight: 600, marginBottom: 2, paddingRight: isStart || isEnd ? 28 : 0 }}>
        {data.label}
      </div>
      <div style={{ color: "#94a3b8", fontSize: 11 }}>{data.role}</div>

      <Handle
        type="source"
        position={Position.Bottom}
        style={{ background: isEnd ? "#f87171" : "#7c6af7", opacity: isEnd ? 0.2 : 1 }}
      />
    </div>
  );
}

const nodeTypes = { agentNode: AgentNode };
const edgeTypes = { feedback: FeedbackEdge };

const edgeStyle = (condition) => ({
  animated: true,
  label: condition || undefined,
  labelStyle: { fill: "#f59e0b", fontSize: 11, fontWeight: 600 },
  labelBgStyle: { fill: "#1a1d2e", fillOpacity: 0.9 },
  style: { stroke: condition ? "#f59e0b" : "#7c6af7", strokeWidth: 2 },
  markerEnd: { type: MarkerType.ArrowClosed, color: condition ? "#f59e0b" : "#7c6af7", width: 20, height: 20 },
});

export default function WorkflowCanvas({ initialNodes, initialEdges, onChange }) {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes || []);
  const [edges, setEdges, onEdgesChange] = useEdgesState(
    (initialEdges || []).map((e) => ({ ...e, ...edgeStyle(e.data?.condition), type: e.type || "default" }))
  );
  const reactFlowWrapper = useRef(null);
  const [conditionPanel, setConditionPanel] = useState(null); // { edgeId, condition }

  // Compute isStart / isEnd from current edge topology
  const nodesWithMeta = useMemo(() => {
    const targetIds = new Set(edges.map((e) => e.target));
    const sourceIds = new Set(edges.map((e) => e.source));
    return nodes.map((n) => ({
      ...n,
      data: {
        ...n.data,
        isStart: !targetIds.has(n.id),
        isEnd: !sourceIds.has(n.id),
      },
    }));
  }, [nodes, edges]);

  const onConnect = useCallback(
    (params) => {
      const srcNode = nodes.find((n) => n.id === params.source);
      const tgtNode = nodes.find((n) => n.id === params.target);
      const isBackward = srcNode && tgtNode && srcNode.position.y > tgtNode.position.y;
      const newEdges = addEdge({
        ...params,
        data: {},
        type: isBackward ? "feedback" : "default",
        ...edgeStyle(null),
      }, edges);
      setEdges(newEdges);
      onChange?.({ nodes, edges: newEdges });
    },
    [edges, nodes, onChange]
  );

  const onEdgeClick = useCallback((_, edge) => {
    setConditionPanel({ edgeId: edge.id, condition: edge.data?.condition || "" });
  }, []);

  function saveCondition() {
    const condition = conditionPanel.condition.trim() || null;
    const newEdges = edges.map((e) =>
      e.id === conditionPanel.edgeId
        ? { ...e, data: { ...e.data, condition }, ...edgeStyle(condition) }
        : e
    );
    setEdges(newEdges);
    onChange?.({ nodes, edges: newEdges });
    setConditionPanel(null);
  }

  const onNodesChangeWrapped = useCallback(
    (changes) => {
      onNodesChange(changes);
      // Apply changes locally to get the updated list for onChange
      const updated = changes.reduce((acc, change) => {
        if (change.type === "remove") return acc.filter((n) => n.id !== change.id);
        return acc;
      }, nodes);
      onChange?.({ nodes: updated, edges });
    },
    [nodes, edges, onChange, onNodesChange]
  );

  const onEdgesChangeWrapped = useCallback(
    (changes) => {
      onEdgesChange(changes);
      const updated = changes.reduce((acc, change) => {
        if (change.type === "remove") return acc.filter((e) => e.id !== change.id);
        return acc;
      }, edges);
      onChange?.({ nodes, edges: updated });
    },
    [nodes, edges, onChange, onEdgesChange]
  );

  const onDrop = useCallback(
    (event) => {
      event.preventDefault();
      const data = JSON.parse(event.dataTransfer.getData("application/forge-agent"));
      const bounds = reactFlowWrapper.current.getBoundingClientRect();
      const position = {
        x: event.clientX - bounds.left - 70,
        y: event.clientY - bounds.top - 20,
      };
      const newNode = {
        id: `node-${Date.now()}`,
        type: "agentNode",
        position,
        data: { label: data.name, role: data.role, agent_id: data.id },
      };
      const newNodes = [...nodes, newNode];
      setNodes(newNodes);
      onChange?.({ nodes: newNodes, edges });
    },
    [nodes, edges, onChange, setNodes]
  );

  const onDragOver = useCallback((event) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
  }, []);

  return (
    <div ref={reactFlowWrapper} style={{ width: "100%", height: "100%" }}>
      {conditionPanel && (
        <div style={{
          position: "absolute", top: 12, right: 12, zIndex: 10,
          background: "#1a1d2e", border: "1px solid #f59e0b", borderRadius: 8,
          padding: "12px 14px", display: "flex", flexDirection: "column", gap: 8, minWidth: 240,
        }}>
          <p style={{ fontSize: 12, color: "#f59e0b", margin: 0, fontWeight: 600 }}>Edge Condition</p>
          <p style={{ fontSize: 11, color: "#64748b", margin: 0 }}>
            Only follow this edge if the agent's output contains this keyword.
          </p>
          <input
            autoFocus
            value={conditionPanel.condition}
            onChange={(e) => setConditionPanel((p) => ({ ...p, condition: e.target.value }))}
            onKeyDown={(e) => e.key === "Enter" && saveCondition()}
            placeholder="e.g. urgent, approved, retry…"
            style={{ background: "#0f1117", border: "1px solid #f59e0b", borderRadius: 6, padding: "6px 10px", color: "#e2e8f0", fontSize: 13 }}
          />
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn btn-ghost" style={{ flex: 1, fontSize: 12 }} onClick={() => setConditionPanel(null)}>Cancel</button>
            <button className="btn btn-primary" style={{ flex: 1, fontSize: 12, background: "#f59e0b", borderColor: "#f59e0b" }} onClick={saveCondition}>Save</button>
          </div>
        </div>
      )}

      <ReactFlow
        nodes={nodesWithMeta}
        edges={edges}
        onNodesChange={onNodesChangeWrapped}
        onEdgesChange={onEdgesChangeWrapped}
        onConnect={onConnect}
        onEdgeClick={onEdgeClick}
        onDrop={onDrop}
        onDragOver={onDragOver}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        deleteKeyCode={["Backspace", "Delete"]}
        fitView
      >
        <Background color="#2d3148" gap={20} />
        <Controls />
        <MiniMap nodeColor={(n) => n.data?.isStart ? "#4ade80" : n.data?.isEnd ? "#f87171" : "#7c6af7"} maskColor="rgba(15,17,23,0.8)" />
      </ReactFlow>
    </div>
  );
}
