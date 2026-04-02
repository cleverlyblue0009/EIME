import {
  mockDivergence,
  mockExecutionTrace,
  mockGraph,
  mockIntentTrace,
  mockMetrics,
  mockSimulation,
} from "../utils/mockData";

type AnalyzePayload = {
  code?: string;
  scenario?: string;
  input_size?: number;
  branch_behavior?: string;
};

export async function analyzeCode(payload: AnalyzePayload) {
  try {
    const response = await fetch("/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      throw new Error("Failed to reach backend");
    }
    return await response.json();
  } catch (error) {
    return {
      execution_trace: mockExecutionTrace,
      intent_trace: mockIntentTrace,
      divergence: mockDivergence,
      graph: mockGraph,
      metrics: mockMetrics,
    };
  }
}

type SimulationPayload = {
  scenario?: string;
  input_size?: number;
  branch_behavior?: string;
};

export async function simulateScenario(payload: SimulationPayload) {
  try {
    const response = await fetch("/simulate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      throw new Error("Simulation endpoint error");
    }
    return await response.json();
  } catch (error) {
    return mockSimulation;
  }
}
