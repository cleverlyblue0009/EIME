export const mockCode = `# Fibonacci with intent modeling
from functools import lru_cache

@lru_cache(maxsize=None)
def compute_sequence(limit: int):
    if limit <= 0:
        return []
    result = []
    a, b = 0, 1
    while len(result) < limit:
        result.append(a)
        a, b = b, a + b
    return result

print(compute_sequence(10))
`;

export const mockExecutionTrace = [
  {
    id: "exec-1",
    label: "def compute_sequence(limit: int):",
    line: 1,
    duration_ms: 2.1,
    type: "actual",
    variables: { limit: "10" },
  },
  {
    id: "exec-2",
    label: "if limit <= 0: return []",
    line: 3,
    duration_ms: 3.4,
    type: "actual",
    variables: { decision: "limit > 0" },
  },
  {
    id: "exec-3",
    label: "loop while len(result) < limit",
    line: 6,
    duration_ms: 5.2,
    type: "actual",
    variables: { iterations: "10" },
  },
  {
    id: "exec-4",
    label: "result.append(a)",
    line: 7,
    duration_ms: 4.8,
    type: "actual",
    variables: { a: "0", result: "[0]" },
  },
  {
    id: "exec-5",
    label: "a, b = b, a + b",
    line: 8,
    duration_ms: 6.1,
    type: "actual",
    variables: { next: "1" },
  },
  {
    id: "exec-6",
    label: "return result",
    line: 10,
    duration_ms: 7.3,
    type: "actual",
    variables: { size: "9" },
  },
];

export const mockIntentTrace = [
  {
    id: "intent-1",
    label: "Function compute_sequence registers limit",
    line: 1,
    duration_ms: 4.2,
    type: "intended",
    variables: {},
  },
  {
    id: "intent-2",
    label: "Loop constructs full list up to limit",
    line: 6,
    duration_ms: 6.5,
    type: "intended",
    variables: {},
  },
  {
    id: "intent-3",
    label: "Return sequence with limit+1 length",
    line: 10,
    duration_ms: 5.3,
    type: "intended",
    variables: { confidence: "high" },
  },
];

export const mockDivergence = {
  first_divergence: "return result",
  first_divergence_node: "node-exec-6",
  score: 0.87,
  severity: "HIGH",
  confidence: 0.87,
  causal_chain: [
    "Execution stops at a shorter range than the intent model predicted",
    "Loop exit triggered before the final element is materialized",
  ],
  highlights: ["exec-6"],
};

export const mockGraph = {
  nodes: [
    { id: "node-start", label: "Start", type: "meta", status: "active", highlight: false },
    {
      id: "node-intended",
      label: "Intended Flow",
      type: "intended",
      status: "stable",
      highlight: false,
    },
    {
      id: "node-actual",
      label: "Actual Flow",
      type: "actual",
      status: "running",
      highlight: false,
    },
    {
      id: "node-exec-6",
      label: "FIRST DIVERGENCE",
      type: "divergence",
      status: "critical",
      highlight: true,
    },
  ],
  edges: [
    { id: "edge-1", source: "node-start", target: "node-intended", type: "intended", highlight: false },
    { id: "edge-2", source: "node-start", target: "node-actual", type: "actual", highlight: false },
    { id: "edge-3", source: "node-actual", target: "node-exec-6", type: "divergence", highlight: true },
    { id: "edge-4", source: "node-intended", target: "node-exec-6", type: "intended", highlight: false },
  ],
  first_divergence: "node-exec-6",
};

export const mockMetrics = {
  intent_confidence: "88%",
  alignment_score: "MEDIUM",
  divergence_severity: "HIGH",
};

export const mockReasoning = {
  intended:
    "Function compute_sequence(limit) should return every Fibonacci number between index 0 and limit - 1. Expected length: 10 elements.",
  actual:
    "Returns result[:-1] — last element silently dropped. Actual output contains 9 elements, missing fib(9) = 34.",
  divergence:
    "Semantic divergence at line 17. Off-by-one slice produces structurally incorrect output. Divergence score: 0.87 / 1.0.",
  rootCause:
    "Slice [: -1] on line 17 excludes final computed value. Intent model predicts return of complete range; execution terminates one index short.",
  suggestedFix:
    "Adjust loop termination or return slice to include the final computed value. Pass limit + 1 to the range when tracing execution.",
};

export const mockSimulation = {
  scenario: "Base",
  status: "ready",
  message: "Simulation completed for Base scenario with 48 inputs and deterministic branching.",
  metrics: {
    started_at: "2026-04-02T09:37:22Z",
    divergence_risk: "0.31",
    severity: "MEDIUM",
  },
};

export const mockTimeline = {
  frame: 13,
  latency: "17.2ms",
  progress: 42,
};
