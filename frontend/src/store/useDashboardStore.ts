import { create } from "zustand";

import { analyzeCode, simulateScenario } from "../hooks/useApi";
import type {
  BackendGraphPayload,
  DivergencePayload,
  ExecutionEntry,
  IntentEntry,
} from "../utils/graphBuilder";

type GraphPayload = BackendGraphPayload & {
  nodes: NonNullable<BackendGraphPayload["nodes"]>;
  edges: NonNullable<BackendGraphPayload["edges"]>;
  first_divergence?: string;
};

type Divergence = DivergencePayload & {
  score?: number;
  severity?: string;
  causal_chain?: string[];
};

type SimulationResult = {
  scenario: string;
  status: string;
  message: string;
  metrics: Record<string, string>;
};

type Timeline = {
  currentFrame: number;
  totalFrames: number;
  latency: string;
  progress: number;
};

type SimulationOverrides = {
  variables: Record<string, string>;
  condition: string;
  conditionLine?: number;
};

type DashboardState = {
  code: string;
  executionTrace: ExecutionEntry[];
  intentTrace: IntentEntry[];
  intentResult: Record<string, any>;
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
  selectedNodeId: string | null;
  simulationOverrides: SimulationOverrides;
  analyze: (code?: any) => Promise<void>;
  simulate: () => Promise<void>;
  simulateWithOverrides: () => Promise<void>;
  setSelectedNodeId: (value: string | null) => void;
  setCurrentFrame: (value: number) => void;
  setScenario: (value: string) => void;
  setInputSize: (value: number) => void;
  setBranchBehavior: (value: "deterministic" | "random") => void;
  setCode: (value: string) => void;
  setVariableOverride: (key: string, value: string) => void;
  setConditionOverride: (value: string, line?: number) => void;
  clearOverrides: () => void;
};

const formatMetrics = (metrics?: Record<string, unknown>) =>
  Object.fromEntries(
    Object.entries(metrics ?? {}).map(([key, value]) => [key, String(value)])
  );

const normalizeReasoning = (reasoning?: Record<string, any>) => ({
  intended: String(reasoning?.intended_behavior ?? reasoning?.intended ?? ""),
  actual: String(reasoning?.actual_behavior ?? reasoning?.actual ?? ""),
  divergence: String(
    reasoning?.divergence_explanation ??
      reasoning?.divergence_summary ??
      reasoning?.divergence ??
      ""
  ),
  rootCause: String(reasoning?.root_cause ?? reasoning?.rootCause ?? ""),
  suggestedFix: String(
    reasoning?.fix_suggestion ??
      reasoning?.suggested_fix ??
      reasoning?.suggestedFix ??
      ""
  ),
});

const buildTimeline = (executionTrace: any[]) => {
  const totalFrames = executionTrace.length || 0;
  const currentFrame = totalFrames > 0 ? 1 : 0;
  return {
    currentFrame,
    totalFrames,
    latency:
      executionTrace.length > 0
        ? `${executionTrace
            .reduce((sum, t) => sum + (t.duration_ms || 0), 0)
            .toFixed(1)}ms`
        : "0ms",
    progress: totalFrames > 0 ? Math.round((currentFrame / totalFrames) * 100) : 0,
  };
};

const normalizeExecutionTrace = (data: Record<string, any>) => {
  const normalizedSteps = data.normalized_trace?.steps ?? [];
  if (normalizedSteps.length > 0) {
    return normalizedSteps.map((step: any, index: number) => ({
      step: index + 1,
      line: step.lineno ?? 0,
      event: step.context?.toLowerCase?.() ?? "line",
      locals: Object.fromEntries(
        Object.entries(step.variable_deltas ?? {}).map(([key, delta]: [string, any]) => [
          key,
          delta?.to,
        ])
      ),
      func: step.function_name ?? "<module>",
      duration_ms: 0,
    }));
  }
  return data.execution_trace ?? [];
};

const normalizeIntentTrace = (data: Record<string, any>) => {
  const graphNodes = data.graph?.nodes ?? [];
  const fromGraph = graphNodes
    .filter((node: any) => node.type === "intent")
    .map((node: any, index: number) => ({
      step: index + 1,
      line: node.detail?.code_ref?.lineno ?? 0,
      expected_state: node.label,
      expected_locals: node.detail?.variable_snapshot ?? {},
      invariant: node.detail?.invariants_checked?.[0] ?? "",
    }));

  if (fromGraph.length > 0) {
    return fromGraph;
  }

  return data.intent_result?.intent_trace ?? [];
};

const normalizeDivergence = (data: Record<string, any>) => {
  const divergences = data.divergences ?? [];
  const top = divergences[0];
  if (!top) {
    return {
      first_divergence: "",
      score: 0,
      severity: "UNKNOWN",
      causal_chain: [],
      mismatches: [],
    };
  }

  return {
    first_divergence: top.type ?? "",
    score: data.metrics?.divergence_score ?? 0,
    severity: top.severity ?? "UNKNOWN",
    causal_chain: (top.causal_chain ?? []).map((step: any) => ({
      line: step.lineno,
      reason: step.description ?? step.why_this_matters,
    })),
    mismatches: divergences.map((div: any) => ({
      step: undefined,
      line: div.first_occurrence_line ?? div.symptom_line ?? 0,
      type: div.type,
      description: div.actual_behavior ?? div.algorithm_context ?? div.type,
    })),
  };
};

const normalizeGraph = (data: Record<string, any>) =>
  data.graph ?? { nodes: [], edges: [], first_divergence: "" };

const normalizeAnalysisPayload = (data: Record<string, any>) => {
  const trace = normalizeExecutionTrace(data);
  return {
    executionTrace: trace,
    intentTrace: normalizeIntentTrace(data),
    intentResult: data.intent_model ?? data.intent_result ?? {},
    divergence: normalizeDivergence(data),
    graph: normalizeGraph(data),
    reasoning: normalizeReasoning(data.reasoning),
    metrics: formatMetrics(data.metrics ?? {}),
    timeline: buildTimeline(trace),
  };
};

const applyOverridesToCode = (
  code: string,
  overrides: SimulationOverrides
) => {
  const lines = code.split("\n");
  const startMarker = "# --- EIME SIM OVERRIDES START ---";
  const endMarker = "# --- EIME SIM OVERRIDES END ---";

  const startIdx = lines.findIndex((line) => line.trim() === startMarker);
  const endIdx = lines.findIndex((line) => line.trim() === endMarker);
  if (startIdx !== -1 && endIdx !== -1 && endIdx > startIdx) {
    lines.splice(startIdx, endIdx - startIdx + 1);
  }

  if (overrides.condition && overrides.conditionLine) {
    const targetIndex = overrides.conditionLine - 1;
    if (lines[targetIndex]) {
      const line = lines[targetIndex];
      const ifMatch = line.match(/^(\s*if\s+)(.*)(:\s*)$/);
      const whileMatch = line.match(/^(\s*while\s+)(.*)(:\s*)$/);
      if (ifMatch) {
        lines[targetIndex] = `${ifMatch[1]}${overrides.condition}${ifMatch[3]}`;
      } else if (whileMatch) {
        lines[targetIndex] = `${whileMatch[1]}${overrides.condition}${whileMatch[3]}`;
      }
    }
  }

  const overrideLines = Object.entries(overrides.variables).map(
    ([key, value]) => `${key} = ${value}`
  );

  if (overrideLines.length > 0) {
    lines.unshift(
      startMarker,
      ...overrideLines,
      endMarker
    );
  }

  return lines.join("\n");
};

export const useDashboardStore = create<DashboardState>((set, get) => ({
  code: "",
  executionTrace: [],
  intentTrace: [],
  intentResult: {},
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
    currentFrame: 0,
    totalFrames: 0,
    latency: "0ms",
    progress: 0,
  },
  apiError: null,
  scenario: "Base",
  inputSize: 48,
  branchBehavior: "deterministic",
  isAnalyzing: false,
  selectedNodeId: null,
  simulationOverrides: {
    variables: {},
    condition: "",
  },

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
      const normalized = normalizeAnalysisPayload(data);
      set({
        executionTrace: normalized.executionTrace,
        intentTrace: normalized.intentTrace,
        intentResult: normalized.intentResult,
        divergence: normalized.divergence,
        graph: normalized.graph,
        reasoning: normalized.reasoning,
        metrics: normalized.metrics,
        timeline: normalized.timeline,
        isAnalyzing: false,
        apiError: null,
        selectedNodeId: null,
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

      console.log("SIMULATE RESPONSE:", data);
      const normalized = normalizeAnalysisPayload(data);
      set({
        executionTrace: normalized.executionTrace,
        intentTrace: normalized.intentTrace,
        intentResult: normalized.intentResult,
        divergence: normalized.divergence,
        graph: normalized.graph,
        reasoning: normalized.reasoning,
        metrics: normalized.metrics,
        timeline: normalized.timeline,
        simulation: {
          scenario: get().scenario,
          status: "ready",
          message: `Simulation reran intent modeling with ${
            payload.input_size ?? 0
          } inputs (${get().branchBehavior}).`,
          metrics: {
            started_at: new Date().toISOString(),
            divergence_risk: String(data.metrics?.divergence_score ?? 0),
            severity: data.divergences?.[0]?.severity ?? "UNKNOWN",
          },
        },
        apiError: null,
        selectedNodeId: null,
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

  simulateWithOverrides: async () => {
    const safeCode = typeof get().code === "string" ? get().code : "";
    const patchedCode = applyOverridesToCode(safeCode, get().simulationOverrides);
    const payload = {
      input_size: get().inputSize,
      branch_mode: get().branchBehavior,
      code: patchedCode,
      overrides: get().simulationOverrides,
    };

    try {
      const data = await simulateScenario(payload);
      const normalized = normalizeAnalysisPayload(data);
      set({
        executionTrace: normalized.executionTrace,
        intentTrace: normalized.intentTrace,
        intentResult: normalized.intentResult,
        divergence: normalized.divergence,
        graph: normalized.graph,
        reasoning: normalized.reasoning,
        metrics: normalized.metrics,
        timeline: normalized.timeline,
        simulation: {
          scenario: get().scenario,
          status: "ready",
          message: `Simulation updated with overrides.`,
          metrics: {
            started_at: new Date().toISOString(),
            divergence_risk: String(data.metrics?.divergence_score ?? 0),
            severity: data.divergences?.[0]?.severity ?? "UNKNOWN",
          },
        },
        apiError: null,
        selectedNodeId: null,
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

  setSelectedNodeId: (value: string | null) => set({ selectedNodeId: value }),
  setCurrentFrame: (value: number) =>
    set((state) => {
      const totalFrames = state.timeline.totalFrames;
      const clamped = Math.min(Math.max(value, 0), totalFrames || value);
      return {
        timeline: {
          ...state.timeline,
          currentFrame: clamped,
          progress:
            totalFrames > 0
              ? Math.round((clamped / totalFrames) * 100)
              : 0,
        },
      };
    }),
  setScenario: (value: string) => set({ scenario: value }),
  setInputSize: (value: number) => set({ inputSize: value }),
  setBranchBehavior: (value: "deterministic" | "random") => set({ branchBehavior: value }),
  setCode: (value: string) => set({ code: value }),
  setVariableOverride: (key: string, value: string) =>
    set((state) => ({
      simulationOverrides: {
        ...state.simulationOverrides,
        variables: { ...state.simulationOverrides.variables, [key]: value },
      },
    })),
  setConditionOverride: (value: string, line?: number) =>
    set((state) => ({
      simulationOverrides: {
        ...state.simulationOverrides,
        condition: value,
        conditionLine: line ?? state.simulationOverrides.conditionLine,
      },
    })),
  clearOverrides: () =>
    set({
      simulationOverrides: { variables: {}, condition: "", conditionLine: undefined },
    }),
}));
