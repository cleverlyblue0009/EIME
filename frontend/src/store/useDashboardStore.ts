import { create } from "zustand";

import { analyzeCode, simulateScenario } from "../hooks/useApi";

type Trace = {
  id: string;
  label: string;
  line?: number | null;
  duration_ms: number;
  type: "actual" | "intended";
};

type GraphPayload = {
  nodes: Array<{ id: string; label: string; type: string; highlight?: boolean }>;
  edges: Array<{ id: string; source: string; target: string; type: string; highlight?: boolean }>;
  first_divergence: string;
};

type Divergence = {
  first_divergence: string;
  score: number;
  severity: string;
  causal_chain: string[];
};

type SimulationResult = {
  scenario: string;
  status: string;
  message: string;
  metrics: Record<string, string>;
};

type Timeline = {
  frame: number;
  latency: string;
  progress: number;
};

type DashboardState = {
  code: string;
  executionTrace: Trace[];
  intentTrace: Trace[];
  divergence: Divergence;
  graph: GraphPayload;
  metrics: Record<string, string>;
  reasoning: Record<string, string>;
  simulation: SimulationResult;
  timeline: Timeline;
  scenario: string;
  apiError: string | null;
  inputSize: number;
  branchBehavior: "deterministic" | "random";
  isAnalyzing: boolean;
  analyze: (code?: any) => Promise<void>;
  simulate: () => Promise<void>;
  setScenario: (value: string) => void;
  setInputSize: (value: number) => void;
  setBranchBehavior: (value: "deterministic" | "random") => void;
  setCode: (value: string) => void;
};

const formatMetrics = (metrics?: Record<string, unknown>) =>
  Object.fromEntries(
    Object.entries(metrics ?? {}).map(([key, value]) => [key, String(value)])
  );

const normalizeReasoning = (reasoning?: Record<string, any>) => ({
  intended: String(reasoning?.intended_behavior ?? reasoning?.intended ?? ""),
  actual: String(reasoning?.actual_behavior ?? reasoning?.actual ?? ""),
  divergence: String(reasoning?.divergence_summary ?? reasoning?.divergence ?? ""),
  rootCause: String(reasoning?.root_cause ?? reasoning?.rootCause ?? ""),
  suggestedFix: String(reasoning?.suggested_fix ?? reasoning?.suggestedFix ?? ""),
});

const buildTimeline = (executionTrace: any[]) => {
  const totalFrames = executionTrace.length || 1;
  return {
    frame: totalFrames > 0 ? totalFrames : 0,
    latency: executionTrace.length > 0 ? `${executionTrace.reduce((sum, t) => sum + (t.duration_ms || 0), 0).toFixed(1)}ms` : "0ms",
    progress: 0,
  };
};

export const useDashboardStore = create<DashboardState>((set, get) => ({
  code: "",
  executionTrace: [],
  intentTrace: [],
  divergence: {
    first_divergence: "",
    score: 0,
    severity: "UNKNOWN",
    causal_chain: [],
  },
  graph: {
    nodes: [],
    edges: [],
    first_divergence: "",
  },
  metrics: {},
  reasoning: {
    intended: "",
    actual: "",
    divergence: "",
    rootCause: "",
    suggestedFix: "",
  },
  simulation: {
    scenario: "Base",
    status: "idle",
    message: "Start by analyzing a code snippet.",
    metrics: {
      started_at: new Date().toISOString(),
      divergence_risk: "0",
      severity: "UNKNOWN",
    },
  },
  timeline: {
    frame: 0,
    latency: "0ms",
    progress: 0,
  },
  apiError: null,
  scenario: "Base",
  inputSize: 48,
  branchBehavior: "deterministic",
  isAnalyzing: false,

  // ✅ FIXED analyze
  analyze: async (codeOverride?: any) => {
    set({ isAnalyzing: true });

    const safeCode =
      typeof codeOverride === "string"
        ? codeOverride
        : get().code;

    const payload = {
      code: safeCode,
    };

    try {
      const data = await analyzeCode(payload);

      console.log("ANALYZE RESPONSE:", data);

      const trace = data.execution_trace ?? [];
      set({
        executionTrace: trace,
        intentTrace: Array.isArray(data.intent_result) ? data.intent_result : [],
        divergence: data.divergence ?? { first_divergence: "", score: 0, severity: "UNKNOWN", causal_chain: [] },
        graph: data.graph ?? { nodes: [], edges: [], first_divergence: "" },
        reasoning: normalizeReasoning(data.reasoning),
        metrics: formatMetrics(data.metrics ?? {}),
        timeline: buildTimeline(trace),
        isAnalyzing: false,
        apiError: null,
      });
    } catch (error) {
      console.error("Analyze failed:", error);
      set({
        isAnalyzing: false,
        apiError: (error as Error)?.message ?? "Analyze failed",
      });
    }
  },

  // ✅ FIXED simulate (safe code handling)
  simulate: async () => {
    const safeCode =
      typeof get().code === "string" ? get().code : "";

    const payload = {
      input_size: get().inputSize,
      branch_mode: get().branchBehavior,
      code: safeCode,
    };

    try {
      const data = await simulateScenario(payload);
      const formattedMetrics = formatMetrics(data.metrics ?? {});

      console.log("SIMULATE RESPONSE:", data);

      const trace = data.execution_trace ?? [];
      set({
        executionTrace: trace,
        intentTrace: Array.isArray(data.intent_result) ? data.intent_result : [],
        divergence: data.divergence ?? { first_divergence: "", score: 0, severity: "UNKNOWN", causal_chain: [] },
        graph: data.graph ?? { nodes: [], edges: [], first_divergence: "" },
        reasoning: normalizeReasoning(data.reasoning),
        metrics: formattedMetrics,
        timeline: buildTimeline(trace),
        simulation: {
          scenario: get().scenario,
          status: "ready",
          message: `Simulation reran intent modeling with ${
            payload.input_size ?? 0
          } inputs (${get().branchBehavior}).`,
          metrics: {
            started_at: new Date().toISOString(),
            divergence_risk: String(data.divergence?.score ?? 0),
            severity: data.divergence?.severity ?? "UNKNOWN",
          },
        },
        apiError: null,
      });
    } catch (error) {
      console.error("Simulation failed:", error);
      set({
        simulation: {
          scenario: get().scenario,
          status: "error",
          message: `Simulation failed: ${(error as Error)?.message ?? "Unknown error"}`,
          metrics: {
            started_at: new Date().toISOString(),
            divergence_risk: "0",
            severity: "UNKNOWN",
          },
        },
        apiError: (error as Error)?.message ?? "Simulation failed",
        isAnalyzing: false,
      });
    }
  },

  setScenario: (value: string) => set({ scenario: value }),
  setInputSize: (value: number) => set({ inputSize: value }),
  setBranchBehavior: (value: "deterministic" | "random") => set({ branchBehavior: value }),
  setCode: (value: string) => set({ code: value }),
}));