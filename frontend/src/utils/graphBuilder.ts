import type { Edge, Node } from "reactflow";

export type ExecutionEntry = {
  step?: number;
  line?: number | null;
  event?: string;
  locals?: Record<string, any>;
  func?: string;
  value?: any;
};

export type IntentEntry = {
  step?: number;
  line?: number | null;
  expected_state?: string;
  expected_locals?: Record<string, any>;
  invariant?: string;
};

export type DivergenceMismatch = {
  step?: number;
  line?: number | null;
  type?: string;
  expected?: any;
  actual?: any;
  description?: string;
};

export type DivergencePayload = {
  mismatches?: DivergenceMismatch[];
  first_divergence?: string | null;
};

export type ExecutionNodeData = {
  id: string;
  label: string;
  shortLabel: string;
  line_number: number;
  operation_type: string;
  variables: Record<string, any>;
  function_name: string;
  iteration?: number;
  type: "actual" | "intended" | "divergence";
  code_line?: string;
  step?: number;
  mismatch?: DivergenceMismatch[];
  invariant?: string;
};

export type ExecutionGraphResult = {
  nodes: Array<Node<ExecutionNodeData>>;
  edges: Array<Edge>;
  nodeIdByStep: Record<number, string>;
  codeLines: string[];
};

export type BackendGraphNode = {
  id: string;
  label: string;
  type: string;
  detail?: {
    full_description?: string;
    variable_snapshot?: Record<string, any>;
    code_ref?: { lineno?: number | null };
    role_in_algorithm?: string;
    why_matters?: string;
    invariants_checked?: string[];
  };
};

export type BackendGraphEdge = {
  id: string;
  source: string;
  target: string;
  type: string;
  label?: string | null;
};

export type BackendGraphPayload = {
  nodes?: BackendGraphNode[];
  edges?: BackendGraphEdge[];
  first_divergence?: string;
};

type BuildOptions = {
  collapseLoops?: boolean;
  collapsedFunctions?: Set<string>;
};

const formatLabel = (
  entry: ExecutionEntry,
  codeLine: string | undefined,
  iteration?: number,
  isDivergence?: boolean
) => {
  if (entry.event === "return") {
    const value =
      entry.value !== undefined && entry.value !== null ? ` ${entry.value}` : "";
    return `Return${value}${isDivergence ? " (BUG)" : ""}`;
  }
  if (entry.event === "exception") {
    return `Exception${isDivergence ? " (BUG)" : ""}`;
  }
  if (entry.event === "call") {
    const fn = entry.func ? `${entry.func}()` : "function call";
    return `Call ${fn}${isDivergence ? " (BUG)" : ""}`;
  }
  if (codeLine) {
    const base = codeLine.trim();
    if (iteration && iteration > 1) {
      return `Loop iteration ${iteration}: ${base}${isDivergence ? " (BUG)" : ""}`;
    }
    return `Line ${entry.line ?? "?"}: ${base}${isDivergence ? " (BUG)" : ""}`;
  }
  return `Line ${entry.line ?? "?"}${isDivergence ? " (BUG)" : ""}`;
};

const shorten = (text: string, max = 36) => {
  if (text.length <= max) return text;
  return `${text.slice(0, max - 1).trim()}…`;
};

export function buildExecutionGraph(
  executionTrace: ExecutionEntry[],
  intentTrace: IntentEntry[],
  divergence: DivergencePayload | null,
  code: string,
  options?: BuildOptions
): ExecutionGraphResult {
  const codeLines = code.split("\n");
  const mismatchByStep = new Map<number, DivergenceMismatch[]>();
  const mismatchByLine = new Map<number, DivergenceMismatch[]>();
  (divergence?.mismatches ?? []).forEach((mismatch) => {
    const step = mismatch.step ?? 0;
    const line = mismatch.line ?? 0;
    if (step) {
      mismatchByStep.set(step, [...(mismatchByStep.get(step) ?? []), mismatch]);
    }
    if (line) {
      mismatchByLine.set(line, [...(mismatchByLine.get(line) ?? []), mismatch]);
    }
  });

  const collapsedFunctions = options?.collapsedFunctions ?? new Set<string>();
  const collapseLoops = options?.collapseLoops ?? false;

  const nodes: Array<Node<ExecutionNodeData>> = [];
  const edges: Edge[] = [];
  const nodeIdByStep: Record<number, string> = {};

  const lineIterationMap = new Map<number, number>();
  let previousNodeId: string | null = null;

  const addEdge = (source: string | null, target: string, type: string) => {
    if (!source) return;
    edges.push({
      id: `${source}-${target}-${type}`,
      source,
      target,
      type: "default",
      data: { edgeType: type },
    });
  };

  const shouldCollapseFunction = (fn: string) =>
    fn && collapsedFunctions.has(fn);

  const createActualNode = (
    entry: ExecutionEntry,
    iteration?: number,
    overrideLabel?: string
  ) => {
    const step = entry.step ?? 0;
    const line = entry.line ?? 0;
    const fnName = entry.func || "<module>";
    const isDivergence =
      mismatchByStep.has(step) || mismatchByLine.has(line);
    const label = overrideLabel
      ? overrideLabel
      : formatLabel(entry, codeLines[line - 1], iteration, isDivergence);
    const shortLabel = shorten(label, 34);
    const nodeId = `exec-${step || nodes.length + 1}`;

    const data: ExecutionNodeData = {
      id: nodeId,
      label,
      shortLabel,
      line_number: line,
      operation_type: entry.event ?? "line",
      variables: entry.locals ?? {},
      function_name: fnName,
      iteration,
      type: isDivergence ? "divergence" : "actual",
      code_line: codeLines[line - 1],
      step,
      mismatch: mismatchByStep.get(step) ?? mismatchByLine.get(line),
    };

    nodes.push({
      id: nodeId,
      type: "executionNode",
      data,
      position: { x: 0, y: 0 },
    });
    if (step) {
      nodeIdByStep[step] = nodeId;
    }
    addEdge(previousNodeId, nodeId, "actual");
    previousNodeId = nodeId;
  };

  if (collapseLoops) {
    let bufferEntry: ExecutionEntry | null = null;
    let bufferCount = 0;
    const flushBuffer = () => {
      if (!bufferEntry) return;
      const line = bufferEntry.line ?? 0;
      const label = line
        ? `Line ${line}: ${codeLines[line - 1]?.trim() ?? "loop"} (x${bufferCount})`
        : `Loop block (x${bufferCount})`;
      createActualNode(bufferEntry, bufferCount, label);
      bufferEntry = null;
      bufferCount = 0;
    };

    executionTrace.forEach((entry, idx) => {
      const line = entry.line ?? 0;
      if (entry.event === "line" && line) {
        const count = (lineIterationMap.get(line) ?? 0) + 1;
        lineIterationMap.set(line, count);
        if (!bufferEntry || bufferEntry.line !== line) {
          flushBuffer();
          bufferEntry = entry;
          bufferCount = 1;
        } else {
          bufferCount += 1;
        }
      } else {
        flushBuffer();
        createActualNode(entry, undefined);
      }

      if (idx === executionTrace.length - 1) {
        flushBuffer();
      }
    });
  } else {
    executionTrace.forEach((entry) => {
      const line = entry.line ?? 0;
      let iteration: number | undefined;
      if (line) {
        const next = (lineIterationMap.get(line) ?? 0) + 1;
        lineIterationMap.set(line, next);
        iteration = next;
      }
      createActualNode(entry, iteration);
    });
  }

  const intentNodesByLine = new Map<number, string[]>();
  let previousIntentId: string | null = null;

  intentTrace.forEach((entry) => {
    const step = entry.step ?? nodes.length + 1;
    const line = entry.line ?? 0;
    const labelBase = entry.expected_state
      ? entry.expected_state
      : line
      ? `Intent for line ${line}`
      : "Intent step";
    const label = `Intent: ${labelBase}`;
    const nodeId = `intent-${step}`;
    const data: ExecutionNodeData = {
      id: nodeId,
      label,
      shortLabel: shorten(label, 34),
      line_number: line,
      operation_type: "intent",
      variables: entry.expected_locals ?? {},
      function_name: "intent",
      iteration: entry.step,
      type: "intended",
      code_line: codeLines[line - 1],
      step,
      invariant: entry.invariant,
    };
    nodes.push({
      id: nodeId,
      type: "executionNode",
      data,
      position: { x: 0, y: 0 },
    });
    intentNodesByLine.set(line, [
      ...(intentNodesByLine.get(line) ?? []),
      nodeId,
    ]);
    addEdge(previousIntentId, nodeId, "intended");
    previousIntentId = nodeId;
  });

  (divergence?.mismatches ?? []).forEach((mismatch, idx) => {
    const step = mismatch.step ?? 0;
    const line = mismatch.line ?? 0;
    const actualId = step ? nodeIdByStep[step] : null;
    const intentIds = line ? intentNodesByLine.get(line) : undefined;
    if (actualId && intentIds && intentIds.length > 0) {
      edges.push({
        id: `divergence-${actualId}-${intentIds[0]}-${idx}`,
        source: actualId,
        target: intentIds[0],
        type: "default",
        data: { edgeType: "divergence" },
      });
    }
  });

  if (collapsedFunctions.size > 0) {
    const hiddenNodes = new Set<string>();
    const functionNodeIds = new Map<string, string[]>();
    const hiddenToSummary = new Map<string, string>();
    nodes.forEach((node) => {
      const fnName = node.data.function_name;
      if (shouldCollapseFunction(fnName)) {
        functionNodeIds.set(fnName, [
          ...(functionNodeIds.get(fnName) ?? []),
          node.id,
        ]);
      }
    });

    functionNodeIds.forEach((ids, fn) => {
      ids.forEach((id) => hiddenNodes.add(id));
      const summaryId = `fn-summary-${fn}`;
      const summaryData: ExecutionNodeData = {
        id: summaryId,
        label: `Function ${fn} (collapsed ${ids.length} steps)`,
        shortLabel: shorten(`Function ${fn} (${ids.length} steps)`),
        line_number: 0,
        operation_type: "collapsed",
        variables: {},
        function_name: fn,
        type: "actual",
      };
      nodes.push({
        id: summaryId,
        type: "executionNode",
        data: summaryData,
        position: { x: 0, y: 0 },
      });
      ids.forEach((id) => hiddenToSummary.set(id, summaryId));
    });

    const visibleNodes = nodes.filter((node) => !hiddenNodes.has(node.id));
    const visibleIds = new Set(visibleNodes.map((node) => node.id));
    const filteredEdges: Edge[] = [];
    edges.forEach((edge) => {
      const source =
        hiddenToSummary.get(edge.source) ?? edge.source;
      const target =
        hiddenToSummary.get(edge.target) ?? edge.target;
      if (source === target) {
        return;
      }
      if (visibleIds.has(source) && visibleIds.has(target)) {
        filteredEdges.push({
          ...edge,
          id: `${source}-${target}-${edge.data?.edgeType ?? edge.type ?? "default"}`,
          source,
          target,
          type: "default",
        });
      }
    });

    return {
      nodes: visibleNodes,
      edges: filteredEdges,
      nodeIdByStep,
      codeLines,
    };
  }

  return { nodes, edges, nodeIdByStep, codeLines };
}

const mapBackendNodeType = (type: string): "actual" | "intended" | "divergence" => {
  if (type === "intent") return "intended";
  if (type === "divergence") return "divergence";
  return "actual";
};

const mapBackendEdgeType = (type: string) => {
  if (type === "intent_alignment") return "intended";
  if (type === "intent_violation") return "divergence";
  return "actual";
};

export function buildExecutionGraphFromBackend(
  graph: BackendGraphPayload | null | undefined,
  code: string
): ExecutionGraphResult {
  const codeLines = code.split("\n");
  const nodeIdByStep: Record<number, string> = {};
  let actualStep = 0;

  const nodes: Array<Node<ExecutionNodeData>> = (graph?.nodes ?? []).map((node) => {
    const mappedType = mapBackendNodeType(node.type);
    const lineNumber = node.detail?.code_ref?.lineno ?? 0;
    const step = mappedType === "actual" ? ++actualStep : undefined;
    if (step) {
      nodeIdByStep[step] = node.id;
    }

    const mismatch =
      mappedType === "divergence"
        ? [
            {
              line: lineNumber || undefined,
              description:
                node.detail?.why_matters ??
                node.detail?.full_description ??
                "Divergence detected.",
            },
          ]
        : undefined;

    return {
      id: node.id,
      type: "executionNode",
      position: { x: 0, y: 0 },
      data: {
        id: node.id,
        label: node.label,
        shortLabel: shorten(node.label, 34),
        line_number: lineNumber || 0,
        operation_type: node.type,
        variables: node.detail?.variable_snapshot ?? {},
        function_name:
          mappedType === "intended"
            ? "intent"
            : mappedType === "divergence"
            ? "divergence"
            : "",
        iteration: mappedType === "actual" ? step : undefined,
        type: mappedType,
        code_line:
          lineNumber > 0
            ? codeLines[lineNumber - 1]
            : node.detail?.full_description ?? "",
        step,
        mismatch,
        invariant: node.detail?.invariants_checked?.[0],
      },
    };
  });

  const edges: Array<Edge> = (graph?.edges ?? []).map((edge) => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
    type: "default",
    data: {
      edgeType: mapBackendEdgeType(edge.type),
      label: edge.label,
      rawType: edge.type,
    },
  }));

  return { nodes, edges, nodeIdByStep, codeLines };
}
