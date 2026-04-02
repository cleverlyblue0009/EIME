import { create } from "zustand";

import { analyzeCode, simulateScenario } from "../hooks/useApi";
import {
  mockCode,
  mockExecutionTrace,
  mockIntentTrace,
  mockDivergence,
  mockGraph,
  mockMetrics,
  mockReasoning,
  mockSimulation,
  mockTimeline,
} from "../utils/mockData";

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
  inputSize: number;
  branchBehavior: string;
  isAnalyzing: boolean;
  analyze: (code?: string) => Promise<void>;
  simulate: () => Promise<void>;
  setScenario: (value: string) => void;
  setInputSize: (value: number) => void;
  setBranchBehavior: (value: string) => void;
  setCode: (value: string) => void;
};

export const useDashboardStore = create<DashboardState>((set, get) => ({
  code: mockCode,
  executionTrace: mockExecutionTrace,
  intentTrace: mockIntentTrace,
  divergence: mockDivergence,
  graph: mockGraph,
  metrics: mockMetrics,
  reasoning: mockReasoning,
  simulation: mockSimulation,
  timeline: mockTimeline,
  scenario: "Base",
  inputSize: 48,
  branchBehavior: "deterministic",
  isAnalyzing: false,
  analyze: async (codeOverride?: string) => {
    set({ isAnalyzing: true });
    const payload = {
      code: codeOverride ?? get().code,
      scenario: get().scenario,
      input_size: get().inputSize,
      branch_behavior: get().branchBehavior,
    };
    const data = await analyzeCode(payload);
    set({
      executionTrace: data.execution_trace,
      intentTrace: data.intent_trace,
      divergence: data.divergence,
      graph: data.graph,
      metrics: data.metrics,
      isAnalyzing: false,
    });
  },
  simulate: async () => {
    const payload = {
      scenario: get().scenario,
      input_size: get().inputSize,
      branch_behavior: get().branchBehavior,
    };
    const simulation = await simulateScenario(payload);
    set({ simulation });
  },
  setScenario: (value: string) => set({ scenario: value }),
  setInputSize: (value: number) => set({ inputSize: value }),
  setBranchBehavior: (value: string) => set({ branchBehavior: value }),
  setCode: (value: string) => set({ code: value }),
}));
