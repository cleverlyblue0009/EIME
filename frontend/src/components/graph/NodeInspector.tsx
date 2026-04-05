import React from "react";
import { Sparkles } from "lucide-react";

import { useDashboardStore } from "../../store/useDashboardStore";
import { useDebouncedEffect } from "../../hooks/useDebouncedEffect";
import type { ExecutionNodeData } from "../../utils/graphBuilder";

type NodeInspectorProps = {
  node: ExecutionNodeData | null;
  previousLocals?: Record<string, any>;
  onClose: () => void;
};

const formatValue = (value: any) => {
  if (value === undefined) return "undefined";
  if (value === null) return "null";
  if (typeof value === "string") return JSON.stringify(value);
  return String(value);
};

const NodeInspector: React.FC<NodeInspectorProps> = ({
  node,
  previousLocals,
  onClose,
}) => {
  const {
    inputSize,
    setInputSize,
    branchBehavior,
    simulationOverrides,
    setVariableOverride,
    setConditionOverride,
    simulateWithOverrides,
  } = useDashboardStore((state) => ({
    inputSize: state.inputSize,
    setInputSize: state.setInputSize,
    branchBehavior: state.branchBehavior,
    simulationOverrides: state.simulationOverrides,
    setVariableOverride: state.setVariableOverride,
    setConditionOverride: state.setConditionOverride,
    simulateWithOverrides: state.simulateWithOverrides,
  }));

  const [hasEdits, setHasEdits] = React.useState(false);

  React.useEffect(() => {
    setHasEdits(false);
  }, [node?.id]);

  useDebouncedEffect(
    () => {
      if (node && hasEdits) {
        void simulateWithOverrides();
      }
    },
    [
      simulationOverrides.variables,
      simulationOverrides.condition,
      inputSize,
      branchBehavior,
    ],
    350
  );

  if (!node) {
    return (
      <div className="flex h-full flex-col items-center justify-center rounded-2xl border border-white/10 bg-white/5 px-4 py-6 text-center text-sm text-slate-400">
        Select a node to inspect execution details.
      </div>
    );
  }

  const codeLine = node.code_line?.trim();
  const canOverrideCondition =
    codeLine?.startsWith("if ") || codeLine?.startsWith("while ");

  return (
    <div className="flex h-full flex-col gap-4 rounded-2xl border border-white/10 bg-slate-950/70 p-4 shadow-panel-md">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.4em] text-slate-500">
            Node Inspector
          </p>
          <h3 className="text-lg font-semibold text-white">{node.label}</h3>
        </div>
        <button
          onClick={onClose}
          className="rounded-full border border-white/10 px-3 py-1 text-xs text-slate-300 hover:border-white/30"
        >
          Close
        </button>
      </div>

      <div className="rounded-xl border border-white/10 bg-white/5 p-3 text-xs text-slate-200">
        <p className="text-[10px] uppercase tracking-[0.3em] text-slate-400">
          Code Line
        </p>
        <p className="mt-2 whitespace-pre-wrap text-sm text-white">
          {codeLine || "Unavailable"}
        </p>
        <div className="mt-2 flex flex-wrap gap-2 text-[11px] text-slate-400">
          <span>Function: {node.function_name || "<module>"}</span>
          {node.iteration ? <span>Iteration {node.iteration}</span> : null}
          {node.line_number ? <span>Line {node.line_number}</span> : null}
        </div>
      </div>

      {node.type === "intended" && (node.invariant || node.label) ? (
        <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3 text-xs text-emerald-100">
          <p className="text-[10px] uppercase tracking-[0.3em] text-emerald-200">
            Intent Context
          </p>
          <p className="mt-2 text-sm text-emerald-50">{node.label}</p>
          {node.invariant ? (
            <p className="mt-2 text-[12px] text-emerald-100">
              Invariant: {node.invariant}
            </p>
          ) : null}
        </div>
      ) : null}

      <div className="rounded-xl border border-white/10 bg-white/5 p-3 text-xs text-slate-200">
        <p className="text-[10px] uppercase tracking-[0.3em] text-slate-400">
          Variables
        </p>
        <div className="mt-3 space-y-2">
          {Object.entries(node.variables ?? {}).length === 0 ? (
            <p className="text-xs text-slate-400">No locals captured.</p>
          ) : (
            Object.entries(node.variables ?? {}).map(([key, value]) => {
              const previous = previousLocals?.[key];
              return (
                <div key={key} className="rounded-lg border border-white/5 bg-slate-900/60 p-2">
                  <div className="flex items-center justify-between text-[11px] text-slate-300">
                    <span className="font-semibold text-white">{key}</span>
                    {previous !== undefined ? (
                      <span className="text-[10px] text-slate-500">
                        prev: {formatValue(previous)}
                      </span>
                    ) : null}
                  </div>
                  <input
                    className="mt-2 w-full rounded-lg border border-white/10 bg-slate-950/70 px-2 py-1 text-xs text-white"
                    value={
                      simulationOverrides.variables[key] ?? formatValue(value)
                    }
                    onChange={(event) => {
                      setHasEdits(true);
                      setVariableOverride(key, event.target.value);
                    }}
                  />
                </div>
              );
            })
          )}
        </div>
      </div>

      {node.mismatch && node.mismatch.length > 0 ? (
        <div className="rounded-xl border border-rose-400/30 bg-rose-500/10 p-3 text-xs text-rose-100">
          <p className="text-[10px] uppercase tracking-[0.3em] text-rose-200">
            Divergence Notes
          </p>
          <ul className="mt-2 list-disc pl-4 text-[12px] text-rose-100">
            {node.mismatch.map((item, index) => (
              <li key={`${item.description ?? "mismatch"}-${index}`}>
                {item.description ?? "Mismatch detected."}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="rounded-xl border border-white/10 bg-white/5 p-3 text-xs text-slate-200">
        <p className="text-[10px] uppercase tracking-[0.3em] text-slate-400">
          Loop Bound
        </p>
        <div className="mt-2 flex items-center gap-3">
          <input
            type="range"
            min={1}
            max={200}
            value={inputSize}
            onChange={(event) => {
              setHasEdits(true);
              setInputSize(Number(event.target.value));
            }}
            className="h-1 w-full accent-indigo-500"
          />
          <span className="text-xs text-slate-300">{inputSize}</span>
        </div>
        <p className="mt-2 text-[11px] text-slate-500">
          Adjusts numeric range bounds during simulation.
        </p>
      </div>

      {canOverrideCondition ? (
        <div className="rounded-xl border border-white/10 bg-white/5 p-3 text-xs text-slate-200">
          <p className="text-[10px] uppercase tracking-[0.3em] text-slate-400">
            Condition Override
          </p>
          <input
            className="mt-2 w-full rounded-lg border border-white/10 bg-slate-950/70 px-2 py-1 text-xs text-white"
            placeholder="e.g. i % 2 == 0"
            value={simulationOverrides.condition}
            onChange={(event) => {
              setHasEdits(true);
              setConditionOverride(event.target.value, node.line_number);
            }}
          />
          <p className="mt-2 text-[11px] text-slate-500">
            Rewrites the selected conditional line for this simulation run.
          </p>
        </div>
      ) : null}

      <button
        onClick={() => void simulateWithOverrides()}
        className="mt-auto flex items-center justify-center gap-2 rounded-2xl bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-indigo-500/30 transition hover:bg-indigo-500"
      >
        <Sparkles size={16} />
        Apply Overrides
      </button>
    </div>
  );
};

export default NodeInspector;
