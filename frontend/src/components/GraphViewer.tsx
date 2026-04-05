import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Background,
  BaseEdge,
  Controls,
  Handle,
  MiniMap,
  Position,
  ReactFlow,
  type ReactFlowInstance,
  getBezierPath,
} from "reactflow";

import useIMEAnalysis from "../hooks/useIMEAnalysis";
import useGraphState from "../hooks/useGraphState";

type GraphNodeProps = {
  data: {
    label: string;
    detail?: {
      code_ref?: { lineno?: number };
      step?: number;
      operation?: string;
      hover_summary?: string;
      preview_variables?: Record<string, unknown>;
      group_kind?: string;
      is_divergence_path?: boolean;
    };
    isDimmed?: boolean;
  };
};

const GraphNodeShell = ({
  data,
  toneClass,
  prefix,
}: GraphNodeProps & { toneClass: string; prefix?: string }) => (
  <div
    className={`graph-node-shell ${toneClass} ${data.isDimmed ? "graph-node-dimmed" : ""}`}
    title={data.detail?.hover_summary || data.label}
  >
    <Handle type="target" position={Position.Top} className="graph-node-handle" />
    <div className="graph-node-header">
      <span className="graph-node-label">
        {prefix ? `${prefix} ${data.label}` : data.label}
      </span>
      {data.detail?.code_ref?.lineno ? (
        <span className="graph-node-line">L{data.detail.code_ref.lineno}</span>
      ) : null}
    </div>
    {data.detail?.step || data.detail?.operation ? (
      <div className="graph-node-meta">
        {data.detail?.step ? <span>S{data.detail.step}</span> : null}
        {data.detail?.operation ? <span>{data.detail.operation}</span> : null}
      </div>
    ) : null}
    {data.detail?.hover_summary ? (
      <div className="graph-node-preview">{data.detail.hover_summary}</div>
    ) : null}
    {data.detail?.preview_variables && Object.keys(data.detail.preview_variables).length > 0 ? (
      <div className="graph-node-preview graph-node-state-preview">
        {Object.entries(data.detail.preview_variables)
          .slice(0, 3)
          .map(([key, value]) => `${key}=${JSON.stringify(value)}`)
          .join(" | ")}
      </div>
    ) : null}
    <Handle type="source" position={Position.Bottom} className="graph-node-handle" />
  </div>
);

const ExecutionNode = ({ data }: GraphNodeProps) => (
  <GraphNodeShell data={data} toneClass="node node-execution" />
);

const IntentNode = ({ data }: GraphNodeProps) => (
  <GraphNodeShell data={data} toneClass="node node-intent" />
);

const DivergenceNode = ({ data }: GraphNodeProps) => (
  <GraphNodeShell data={data} toneClass="node node-divergence" prefix="[!]" />
);

const FunctionNode = ({ data }: GraphNodeProps) => (
  <GraphNodeShell data={data} toneClass="node node-function" />
);

const LoopHeaderNode = ({ data }: GraphNodeProps) => (
  <GraphNodeShell data={data} toneClass="node node-loop" />
);

const LoopIterationNode = ({ data }: GraphNodeProps) => (
  <GraphNodeShell data={data} toneClass="node node-loop" />
);

const RecursionNode = ({ data }: GraphNodeProps) => (
  <GraphNodeShell data={data} toneClass="node node-function" />
);

const DataNode = ({ data }: GraphNodeProps) => (
  <GraphNodeShell data={data} toneClass="node node-data" prefix="var" />
);

const ControlFlowEdge = (props: any) => {
  const [edgePath] = getBezierPath(props);
  return <BaseEdge path={edgePath} style={{ stroke: "#6b7280", strokeWidth: 1.5 }} {...props} />;
};

const IntentViolationEdge = (props: any) => {
  const [edgePath] = getBezierPath(props);
  return (
    <BaseEdge
      path={edgePath}
      style={{ stroke: "#e05252", strokeDasharray: "6 4", strokeWidth: 2 }}
      {...props}
    />
  );
};

const DataFlowEdge = (props: any) => {
  const [edgePath] = getBezierPath(props);
  return (
    <BaseEdge
      path={edgePath}
      style={{ stroke: "#9b59f7", strokeDasharray: "2 6", strokeWidth: 1.4 }}
      {...props}
    />
  );
};

const LoopBackEdge = (props: any) => {
  const [edgePath] = getBezierPath(props);
  return <BaseEdge path={edgePath} style={{ stroke: "#94a3b8", strokeWidth: 1.5 }} {...props} />;
};

const nodeTypes = {
  executionNode: ExecutionNode,
  intentNode: IntentNode,
  divergenceNode: DivergenceNode,
  functionNode: FunctionNode,
  loopHeaderNode: LoopHeaderNode,
  loopIterationNode: LoopIterationNode,
  recursionNode: RecursionNode,
  dataNode: DataNode,
};

const edgeTypes = {
  controlFlow: ControlFlowEdge,
  intentViolation: IntentViolationEdge,
  dataFlow: DataFlowEdge,
  loopBack: LoopBackEdge,
};

const GraphViewer = () => {
  const { graphNodes, graphEdges, graphMeta, graphCatalog, selectNode, setActiveGraph } = useIMEAnalysis();
  const {
    graphMode,
    showIntent,
    showData,
    showOnlyDivergence,
    detailLevel,
    setGraphMode,
    toggleIntent,
    toggleData,
    toggleDivergence,
    setDetailLevel,
  } = useGraphState();
  const [isExpanded, setIsExpanded] = useState(false);
  const reactFlowRef = useRef<ReactFlowInstance | null>(null);
  const graphTitle =
    graphMode === "intent"
      ? "Intent Graph"
      : graphMode === "dataflow"
        ? "Data-Flow Graph"
        : graphMode === "execution"
          ? "Execution Graph"
          : "Hybrid Cognitive Graph";

  useEffect(() => {
    setActiveGraph(graphMode);
  }, [graphMode, graphCatalog, setActiveGraph]);

  const filtered = useMemo(() => {
    const levels = graphMeta?.levels ?? {};
    const divergencePathIds = new Set(graphMeta?.divergence_path_node_ids ?? []);
    const graphKind = graphMeta?.graph_kind ?? graphMode;
    const levelNodeIds =
      detailLevel === "function"
        ? new Set(levels.function ?? graphNodes.map((node) => node.id))
        : detailLevel === "loop"
          ? new Set(levels.loop ?? graphNodes.map((node) => node.id))
          : new Set(levels.step ?? graphNodes.map((node) => node.id));

    let nodes = graphNodes.filter((node) => levelNodeIds.has(node.id));
    let edges = graphEdges.filter((edge) => levelNodeIds.has(edge.source) && levelNodeIds.has(edge.target));

    if (!showIntent && graphKind === "hybrid") {
      nodes = nodes.filter((node) => node.type !== "intentNode");
      edges = edges.filter((edge) => edge.type !== "intentViolation");
    }

      if (!showData && graphKind !== "dataflow") {
        nodes = nodes.filter((node) => node.type !== "dataNode");
        const visible = new Set(nodes.map((node) => node.id));
        edges = edges.filter(
          (edge) =>
            visible.has(edge.source) &&
            visible.has(edge.target) &&
            edge.type !== "dataFlow"
        );
      }

    const dimmedNodes =
      showOnlyDivergence && divergencePathIds.size > 0
        ? nodes.map((node) => ({
            ...node,
            data: {
              ...node.data,
              isDimmed: !divergencePathIds.has(node.id) && node.type !== "intentNode",
            },
          }))
        : nodes;

    const dimmedEdges =
      showOnlyDivergence && divergencePathIds.size > 0
        ? edges.map((edge) => ({
            ...edge,
            style:
              divergencePathIds.has(edge.source) && divergencePathIds.has(edge.target)
                ? edge.style
                : { ...(edge.style || {}), opacity: 0.15 },
          }))
        : edges;

    return { nodes: dimmedNodes, edges: dimmedEdges };
  }, [graphNodes, graphEdges, graphMeta, showIntent, showData, showOnlyDivergence, detailLevel, graphMode]);

  const fitGraph = useCallback(
    (duration = 250) => {
      if (!reactFlowRef.current || filtered.nodes.length === 0) {
        return;
      }

      window.requestAnimationFrame(() => {
        reactFlowRef.current?.fitView({
          padding: isExpanded ? 0.08 : 0.14,
          duration,
        });
      });
    },
    [filtered.nodes.length, isExpanded]
  );

  useEffect(() => {
    if (!filtered.nodes.length) {
      return;
    }

    const timer = window.setTimeout(() => fitGraph(0), 50);
    return () => window.clearTimeout(timer);
  }, [filtered.nodes, filtered.edges, isExpanded, fitGraph]);

  useEffect(() => {
    if (!isExpanded) {
      return;
    }

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setIsExpanded(false);
      }
    };

    window.addEventListener("keydown", onKeyDown);

    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [isExpanded]);

  return (
    <div className={`graph-viewer ${isExpanded ? "graph-viewer-expanded" : ""}`}>
      <div className="panel-header graph-toolbar">
        <div>
          <h2 style={{ margin: 0 }}>{graphTitle}</h2>
          <p style={{ margin: 0, color: "var(--text-secondary)" }}>
            Switch between hybrid, execution, intent, and data-flow views while keeping the same interactive canvas.
          </p>
        </div>
        <div className="graph-actions">
          <button className="button-secondary" onClick={() => setGraphMode("hybrid")}>
            Hybrid
          </button>
          <button className="button-secondary" onClick={() => setGraphMode("execution")}>
            Execution
          </button>
          <button className="button-secondary" onClick={() => setGraphMode("intent")}>
            Intent
          </button>
          <button className="button-secondary" onClick={() => setGraphMode("dataflow")}>
            Data Flow
          </button>
          <button className="button-secondary" onClick={() => setDetailLevel("function")}>
            Functions
          </button>
          <button className="button-secondary" onClick={() => setDetailLevel("loop")}>
            Loops
          </button>
          <button className="button-secondary" onClick={() => setDetailLevel("step")}>
            Steps
          </button>
          <button className="button-secondary" onClick={toggleIntent}>
            Intent
          </button>
          <button className="button-secondary" onClick={toggleData}>
            Data
          </button>
          <button className="button-secondary" onClick={toggleDivergence}>
            Divergence Path
          </button>
          <button className="button-secondary" onClick={() => fitGraph()}>
            Fit Graph
          </button>
          <button className="button-secondary" onClick={() => setIsExpanded((value) => !value)}>
            {isExpanded ? "Collapse" : "Expand"}
          </button>
        </div>
      </div>

      <div className="graph-flow-shell">
        <ReactFlow
          nodes={filtered.nodes}
          edges={filtered.edges}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          minZoom={0.05}
          maxZoom={1.5}
          onInit={(instance: ReactFlowInstance) => {
            reactFlowRef.current = instance;
            fitGraph(0);
          }}
          onNodeClick={(_event: unknown, node: { id: string }) => selectNode(node.id)}
          proOptions={{ hideAttribution: true }}
        >
          <Background gap={18} size={1} color="rgba(255,255,255,0.05)" />
          <MiniMap pannable zoomable />
          <Controls />
        </ReactFlow>
      </div>
    </div>
  );
};

export default GraphViewer;
