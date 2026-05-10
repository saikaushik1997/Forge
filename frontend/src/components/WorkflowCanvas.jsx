import { useCallback, useRef } from "react";
import ReactFlow, {
  addEdge,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  Handle,
  Position,
} from "reactflow";
import "reactflow/dist/style.css";

const nodeStyle = {
  background: "#1a1d2e",
  border: "1px solid #7c6af7",
  borderRadius: 10,
  padding: "10px 16px",
  color: "#e2e8f0",
  fontSize: 13,
  minWidth: 140,
};

function AgentNode({ data }) {
  return (
    <div style={nodeStyle}>
      <Handle type="target" position={Position.Top} style={{ background: "#7c6af7" }} />
      <div style={{ fontWeight: 600, marginBottom: 2 }}>{data.label}</div>
      <div style={{ color: "#94a3b8", fontSize: 11 }}>{data.role}</div>
      <Handle type="source" position={Position.Bottom} style={{ background: "#7c6af7" }} />
    </div>
  );
}

const nodeTypes = { agentNode: AgentNode };

export default function WorkflowCanvas({ initialNodes, initialEdges, onChange }) {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes || []);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges || []);
  const reactFlowWrapper = useRef(null);

  const onConnect = useCallback(
    (params) => {
      const newEdges = addEdge({ ...params, animated: true, style: { stroke: "#7c6af7" } }, edges);
      setEdges(newEdges);
      onChange?.({ nodes, edges: newEdges });
    },
    [edges, nodes, onChange]
  );

  const onNodesChangeWrapped = useCallback(
    (changes) => {
      onNodesChange(changes);
      onChange?.({ nodes, edges });
    },
    [nodes, edges, onChange, onNodesChange]
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
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChangeWrapped}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onDrop={onDrop}
        onDragOver={onDragOver}
        nodeTypes={nodeTypes}
        fitView
      >
        <Background color="#2d3148" gap={20} />
        <Controls />
        <MiniMap nodeColor="#7c6af7" maskColor="rgba(15,17,23,0.8)" />
      </ReactFlow>
    </div>
  );
}
