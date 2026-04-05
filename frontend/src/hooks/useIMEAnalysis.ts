import { create } from "zustand";
import dagre from "dagre";

import { simulate as simulateApi } from "../api/client";
import { analyzeCode } from "./useApi";

type IMEState = {
  code: string;
  analysisResult: any;
  selectedNodeId: string | null;
  isAnalyzing: boolean;
  analysisStage: string | null;
  analysisError: string | null;
  graphCatalog: Record<string, { nodes: any[]; edges: any[]; meta: any }>;
  graphNodes: any[];
  graphEdges: any[];
  graphMeta: any;
  geminiApiKey: string;
  setCode: (code: string) => void;
  setGeminiApiKey: (geminiApiKey: string) => void;
  analyze: () => Promise<void>;
  buildGraph: (result: any) => void;
  setActiveGraph: (mode: string) => void;
  selectNode: (nodeId: string | null) => void;
  simulate: (patch: any) => Promise<void>;
};

const DEFAULT_CODE = "";

const nodeWidth = 200;
const nodeHeight = 60;

const mapNodeType = (type: string) => {
  switch (type) {
    case "intent":
      return "intentNode";
    case "divergence":
      return "divergenceNode";
    case "data":
      return "dataNode";
    case "function_entry":
    case "function_exit":
      return "functionNode";
    case "loop_header":
      return "loopHeaderNode";
    case "loop_iteration":
      return "loopIterationNode";
    case "recursion_call":
    case "recursion_base":
      return "recursionNode";
    default:
      return "executionNode";
  }
};

const mapEdgeType = (type: string) => {
  switch (type) {
    case "intent_alignment":
      return "controlFlow";
    case "intent_violation":
      return "intentViolation";
    case "data_flow":
    case "dependency":
    case "mutation":
      return "dataFlow";
    case "loop_back":
      return "loopBack";
    default:
      return "controlFlow";
  }
};

const layoutGraph = (nodes: any[], edges: any[]) => {
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));
  dagreGraph.setGraph({ rankdir: "TB", nodesep: 80, ranksep: 60 });

  nodes.forEach((node) => {
    dagreGraph.setNode(node.id, { width: nodeWidth, height: nodeHeight });
  });
  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target);
  });

  dagre.layout(dagreGraph);

  const layoutedNodes = nodes.map((node) => {
    const pos = dagreGraph.node(node.id);
    return {
      ...node,
      position: { x: pos.x - nodeWidth / 2, y: pos.y - nodeHeight / 2 },
    };
  });

  return { nodes: layoutedNodes, edges };
};

const mapGraph = (graph: any) => {
  const rawNodes = graph?.nodes ?? [];
  const rawEdges = graph?.edges ?? [];
  const graphMeta = graph?.meta ?? {};

  const nodes = rawNodes.map((node: any) => ({
    id: node.id,
    type: mapNodeType(node.type),
    position: node.position || { x: 0, y: 0 },
    data: {
      label: node.label,
      detail: node.detail,
      raw: node,
    },
  }));

  const edges = rawEdges.map((edge: any) => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
    type: mapEdgeType(edge.type),
    animated: edge.animated || edge.type === "intent_violation",
    data: {
      label: edge.label,
      raw: edge,
    },
  }));

  const layouted = layoutGraph(nodes, edges);
  return { nodes: layouted.nodes, edges: layouted.edges, meta: graphMeta };
};

const useIMEAnalysis = create<IMEState>((set, get) => ({
  code: DEFAULT_CODE,
  analysisResult: null,
  selectedNodeId: null,
  isAnalyzing: false,
  analysisStage: null,
  analysisError: null,
  graphCatalog: {},
  graphNodes: [],
  graphEdges: [],
  graphMeta: {},
  geminiApiKey: "",

  setCode: (code) => set({ code, analysisError: null }),
  setGeminiApiKey: (geminiApiKey) => set({ geminiApiKey }),

  analyze: async () => {
    const code = get().code.trim();
    if (!code) {
      set({
        analysisError: "Paste any Python program, function, or script to analyze.",
        analysisStage: "idle",
        isAnalyzing: false,
      });
      return;
    }

    set({
      isAnalyzing: true,
      analysisStage: "analyzing",
      analysisError: null,
    });

    try {
      const result = await analyzeCode({
        code,
        gemini_api_key: get().geminiApiKey || null,
      });
      get().buildGraph(result);
      set({
        analysisResult: result,
        selectedNodeId: null,
        isAnalyzing: false,
        analysisStage: "complete",
        analysisError: null,
      });
    } catch (error) {
      set({
        isAnalyzing: false,
        analysisStage: "error",
        analysisError:
          error instanceof Error ? error.message : "Analysis failed unexpectedly.",
      });
    }
  },

  buildGraph: (result) => {
    const graphCatalog = {
      hybrid: mapGraph(result?.graph),
      execution: mapGraph(result?.execution_graph ?? result?.graph),
      intent: mapGraph(result?.intent_graph ?? result?.graph),
      dataflow: mapGraph(result?.data_flow_graph ?? result?.graph),
    };
    const active = graphCatalog.hybrid;
    set({
      graphCatalog,
      graphNodes: active.nodes,
      graphEdges: active.edges,
      graphMeta: active.meta,
    });
  },

  setActiveGraph: (mode) => {
    const active = get().graphCatalog[mode] || get().graphCatalog.hybrid;
    if (!active) {
      return;
    }
    set({
      graphNodes: active.nodes,
      graphEdges: active.edges,
      graphMeta: active.meta,
      selectedNodeId: null,
    });
  },

  selectNode: (nodeId) => set({ selectedNodeId: nodeId }),

  simulate: async (patch) => {
    const result = await simulateApi(patch);
    set({
      analysisResult: result,
      code: result?.graph?.source ?? get().code,
      analysisError: null,
    });
    get().buildGraph(result);
  },
}));

export default useIMEAnalysis;
