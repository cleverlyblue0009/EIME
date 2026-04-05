import React from "react";
import {
  ReactFlow,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
  Background,
  MiniMap,
  Controls,
  MarkerType,
  type ReactFlowInstance,
} from "reactflow";
import {
  Eye,
  Maximize2,
  Minimize2,
  SlidersHorizontal,
} from "lucide-react";

import { useDashboardStore } from "../store/useDashboardStore";
import LegendPill from "./LegendPill";
import ExecutionNode from "./graph/ExecutionNode";
import NodeInspector from "./graph/NodeInspector";
import {
  buildExecutionGraph,
  buildExecutionGraphFromBackend,
  type BackendGraphPayload,
} from "../utils/graphBuilder";
import { layoutGraph } from "../utils/graphLayout";

const nodeTypes = { executionNode: ExecutionNode };

const GraphPanel: React.FC = () => {
  const code = useDashboardStore((state) => state.code);
  const executionTrace = useDashboardStore((state) => state.executionTrace);
  const intentTrace = useDashboardStore((state) => state.intentTrace);
  const divergence = useDashboardStore((state) => state.divergence);
  const backendGraph = useDashboardStore((state) => state.graph);
  const timeline = useDashboardStore((state) => state.timeline);
  const selectedNodeId = useDashboardStore((state) => state.selectedNodeId);
  const setSelectedNodeId = useDashboardStore((state) => state.setSelectedNodeId);
  const setCurrentFrame = useDashboardStore((state) => state.setCurrentFrame);

  const [isFullscreen, setIsFullscreen] = React.useState(false);
  const [collapseLoops, setCollapseLoops] = React.useState(false);
  const [collapsedFunctions, setCollapsedFunctions] = React.useState<Set<string>>(
    new Set()
  );
  const reactFlowRef = React.useRef<ReactFlowInstance | null>(null);

  const normalizeEdgeForReactFlow = React.useCallback((edge: any) => {
    const edgeType = edge.data?.edgeType ?? edge.type;
    if (edgeType === "divergence") {
      return {
        ...edge,
        type: "default",
        style: { stroke: "#fb7185", strokeWidth: 2 },
        animated: true,
        markerEnd: { type: MarkerType.ArrowClosed },
      };
    }
    if (edgeType === "intended") {
      return {
        ...edge,
        type: "default",
        style: { stroke: "#34d399", strokeWidth: 1.6, strokeDasharray: "5 4" },
        markerEnd: { type: MarkerType.ArrowClosed },
      };
    }
    return {
      ...edge,
      type: "default",
      style: { stroke: "#60a5fa", strokeWidth: 1.4 },
      markerEnd: { type: MarkerType.ArrowClosed },
    };
  }, []);

  const graphResult = React.useMemo(
    () => {
      if ((backendGraph?.nodes?.length ?? 0) > 0) {
        return buildExecutionGraphFromBackend(backendGraph as BackendGraphPayload, code);
      }
      return buildExecutionGraph(executionTrace, intentTrace, divergence, code, {
        collapseLoops,
        collapsedFunctions,
      });
    },
    [
      backendGraph,
      executionTrace,
      intentTrace,
      divergence,
      code,
      collapseLoops,
      collapsedFunctions,
    ]
  );

  const initialNodes = React.useMemo(() => {
    const highlightedId =
      timeline.currentFrame > 0
        ? graphResult.nodeIdByStep[timeline.currentFrame]
        : undefined;
    const withHighlight = graphResult.nodes.map((node) => ({
      ...node,
      selected: node.id === selectedNodeId,
      data: {
        ...node.data,
        isHighlighted: node.id === highlightedId,
      },
    }));
    return layoutGraph(withHighlight, graphResult.edges, {
      direction: "TB",
      rankSep: 110,
      nodeSep: 70,
    });
  }, [graphResult, timeline.currentFrame, selectedNodeId]);

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(
    graphResult.edges.map(normalizeEdgeForReactFlow)
  );

  React.useEffect(() => {
    const highlightedId =
      timeline.currentFrame > 0
        ? graphResult.nodeIdByStep[timeline.currentFrame]
        : undefined;
    const updatedNodes = layoutGraph(
      graphResult.nodes.map((node) => ({
        ...node,
        selected: node.id === selectedNodeId,
        data: {
          ...node.data,
          isHighlighted: node.id === highlightedId,
        },
      })),
      graphResult.edges,
      {
        direction: "TB",
        rankSep: 110,
        nodeSep: 70,
      }
    );
    setNodes(updatedNodes);
    setEdges(graphResult.edges.map(normalizeEdgeForReactFlow));
  }, [graphResult, timeline.currentFrame, selectedNodeId, setNodes, setEdges, normalizeEdgeForReactFlow]);

  React.useEffect(() => {
    if (!reactFlowRef.current || nodes.length === 0) {
      return;
    }

    const timer = window.setTimeout(() => {
      reactFlowRef.current?.fitView({
        padding: isFullscreen ? 0.08 : 0.14,
        duration: 250,
        includeHiddenNodes: true,
      });
    }, 60);

    return () => window.clearTimeout(timer);
  }, [nodes, edges, isFullscreen]);

  const nodeById = React.useMemo(() => {
    const map = new Map<string, any>();
    nodes.forEach((node) => map.set(node.id, node.data));
    return map;
  }, [nodes]);

  const selectedNode = selectedNodeId ? nodeById.get(selectedNodeId) : null;

  const previousLocals = React.useMemo(() => {
    if (!selectedNode?.step) return undefined;
    const stepIndex = executionTrace.findIndex(
      (entry) => entry.step === selectedNode.step
    );
    if (stepIndex > 0) {
      return executionTrace[stepIndex - 1]?.locals ?? {};
    }
    return undefined;
  }, [selectedNode, executionTrace]);

  const uniqueFunctions = React.useMemo(() => {
    const names = new Set<string>();
    graphResult.nodes.forEach((node) => {
      if (node.data.function_name && node.data.function_name !== "intent") {
        names.add(node.data.function_name);
      }
    });
    return Array.from(names);
  }, [graphResult.nodes]);

  React.useEffect(() => {
    const targetNodeId = graphResult.nodeIdByStep[timeline.currentFrame];
    if (!targetNodeId) return;
    const selectedType = selectedNode?.type;
    if (
      (!selectedNodeId || selectedType !== "intended") &&
      targetNodeId !== selectedNodeId
    ) {
      setSelectedNodeId(targetNodeId);
    }
  }, [
    timeline.currentFrame,
    graphResult.nodeIdByStep,
    selectedNodeId,
    selectedNode,
    setSelectedNodeId,
  ]);

  return (
    <ReactFlowProvider>
      <div
        className={`flex flex-col rounded-3xl border border-white/10 bg-slate-950/80 p-4 shadow-panel-2xl transition-all duration-300 ${
          isFullscreen
            ? "fixed inset-0 z-[9999] m-0 rounded-none border-none bg-slate-950 text-white"
            : ""
        }`}
        style={isFullscreen ? { minHeight: "100vh", minWidth: "100vw" } : undefined}
      >
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.4em] text-slate-400">
              Intent · Execution Graph
            </p>
            <h2 className="text-3xl font-bold tracking-tight text-white">
              Interactive Execution Explorer
            </h2>
          </div>
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <button className="flex items-center gap-1 rounded-full border border-white/10 bg-white/5 px-3 py-1 transition hover:border-white hover:bg-white/10">
              <Eye size={14} /> Zoom
            </button>
            <button
              onClick={() => setIsFullscreen((prev) => !prev)}
              className="flex items-center gap-1 rounded-full border border-white/10 bg-white/5 px-3 py-1 transition hover:border-white hover:bg-white/10"
              title={isFullscreen ? "Exit fullscreen" : "Enter fullscreen"}
            >
              {isFullscreen ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
            </button>
          </div>
        </div>

        <div className="mt-4 flex flex-col gap-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex gap-2">
              <LegendPill
                label="Intended"
                color="bg-emerald-500/15 text-emerald-300 border border-emerald-300/40"
              />
              <LegendPill
                label="Actual"
                color="bg-blue-500/15 text-blue-300 border border-blue-300/40"
              />
              <LegendPill
                label="Divergence"
                color="bg-red-500/15 text-red-300 border border-red-300/40"
              />
            </div>
            <div className="flex flex-wrap items-center gap-2 text-xs text-slate-400">
              <button
                onClick={() => setCollapseLoops((prev) => !prev)}
                className="rounded-full border border-white/10 bg-white/5 px-3 py-1 transition hover:border-white/30"
              >
                {collapseLoops ? "Expand loops" : "Collapse loops"}
              </button>
              {uniqueFunctions.map((fn) => {
                const isCollapsed = collapsedFunctions.has(fn);
                return (
                  <button
                    key={fn}
                    onClick={() =>
                      setCollapsedFunctions((prev) => {
                        const next = new Set(prev);
                        if (next.has(fn)) {
                          next.delete(fn);
                        } else {
                          next.add(fn);
                        }
                        return next;
                      })
                    }
                    className={`rounded-full border px-3 py-1 transition ${
                      isCollapsed
                        ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-200"
                        : "border-white/10 bg-white/5 text-slate-300 hover:border-white/30"
                    }`}
                  >
                    {isCollapsed ? `Expand ${fn}` : `Collapse ${fn}`}
                  </button>
                );
              })}
            </div>
          </div>

          <div
            className={`grid gap-4 ${
              isFullscreen ? "lg:grid-cols-[3fr_1.1fr]" : "lg:grid-cols-[2.4fr_1fr]"
            }`}
          >
            <div
              className={`relative w-full overflow-hidden rounded-2xl border border-white/5 bg-gradient-to-br from-slate-900 via-slate-950 to-slate-800/90 shadow-inner ${
                isFullscreen ? "h-[calc(100vh-220px)]" : "h-[520px]"
              }`}
            >
              {nodes.length === 0 ? (
                <div className="absolute inset-0 flex items-center justify-center text-slate-400">
                  No graph data yet. Start analysis to visualize the execution chain.
                </div>
              ) : (
                <ReactFlow
                  nodes={nodes}
                  edges={edges}
                  onNodesChange={onNodesChange}
                  onEdgesChange={onEdgesChange}
                  nodeTypes={nodeTypes}
                  fitView
                  fitViewOptions={{ padding: isFullscreen ? 0.08 : 0.14 }}
                  minZoom={0.2}
                  maxZoom={1.8}
                  onInit={(instance) => {
                    reactFlowRef.current = instance;
                    instance.fitView({
                      padding: isFullscreen ? 0.08 : 0.14,
                      duration: 0,
                      includeHiddenNodes: true,
                    });
                  }}
                  onNodeClick={(_, node) => {
                    setSelectedNodeId(node.id);
                    if (node.data?.step) {
                      setCurrentFrame(node.data.step);
                    }
                  }}
                  onPaneClick={() => setSelectedNodeId(null)}
                  className="bg-transparent"
                >
                  <Background color="#1f2937" gap={22} />
                  <MiniMap
                    nodeColor={(node) => {
                      if (node.data?.type === "divergence") return "#fb7185";
                      if (node.data?.type === "intended") return "#34d399";
                      return "#60a5fa";
                    }}
                    maskColor="rgba(15, 23, 42, 0.7)"
                  />
                  <Controls
                    className="!bg-slate-900/80 !text-white"
                    showInteractive={false}
                  />
                </ReactFlow>
              )}
            </div>

            <NodeInspector
              node={selectedNode}
              previousLocals={previousLocals}
              onClose={() => setSelectedNodeId(null)}
            />
          </div>
        </div>

        <div
          className={`mt-4 flex items-center justify-between rounded-2xl border border-white/5 bg-slate-900/60 px-4 py-3 transition-all duration-300 ${
            isFullscreen ? "hidden" : ""
          }`}
        >
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-slate-400">
              Timeline
            </p>
            <p className="text-sm text-white">
              t = {timeline.latency} · Frame {timeline.currentFrame}
            </p>
          </div>
          <div className="flex items-center gap-3 text-xs text-slate-400">
            <SlidersHorizontal size={16} />
            <div className="flex items-center gap-1 rounded-full border border-white/20 px-3 py-1 text-[11px]">
              {timeline.progress}% loaded
            </div>
          </div>
        </div>
      </div>
    </ReactFlowProvider>
  );
};

export default GraphPanel;
