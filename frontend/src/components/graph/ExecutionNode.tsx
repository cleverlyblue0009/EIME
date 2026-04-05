import React from "react";
import { Handle, Position, type NodeProps } from "reactflow";

import type { ExecutionNodeData } from "../../utils/graphBuilder";

const typeStyles: Record<string, string> = {
  actual: "bg-blue-500/20 text-blue-100 border-blue-400/50",
  intended: "bg-emerald-500/20 text-emerald-100 border-emerald-400/50",
  divergence: "bg-rose-500/25 text-rose-100 border-rose-400/60",
};

type HighlightedExecutionNodeData = ExecutionNodeData & { isHighlighted?: boolean };

const ExecutionNode: React.FC<NodeProps<HighlightedExecutionNodeData>> = ({
  data,
  selected,
}) => {
  const badge = typeStyles[data.type] ?? typeStyles.actual;
  const highlightRing = data.isHighlighted
    ? "ring-2 ring-amber-300/80 shadow-[0_0_35px_rgba(251,191,36,0.35)]"
    : "";

  const borderTone =
    data.type === "divergence" ? "border-rose-400/60" : "border-white/10";

  return (
    <div
      className={`relative min-w-[230px] max-w-[260px] rounded-2xl border ${borderTone} bg-white/5 p-3 text-left text-xs text-white shadow-[0_12px_40px_rgba(15,23,42,0.4)] backdrop-blur-xl transition ${highlightRing} ${
        selected ? "ring-2 ring-white/60" : ""
      }`}
    >
      <Handle type="target" position={Position.Top} className="!bg-white/80" />
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-[10px] uppercase tracking-[0.3em] text-white/50">
            {data.operation_type}
          </p>
          <p className="mt-1 text-sm font-semibold text-white">
            {data.shortLabel}
          </p>
        </div>
        <span
          className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-widest ${badge}`}
        >
          {data.type}
        </span>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-white/70">
        {data.line_number ? (
          <span className="rounded-full border border-white/10 px-2 py-0.5">
            Line {data.line_number}
          </span>
        ) : null}
        {data.iteration && data.iteration > 1 ? (
          <span className="rounded-full border border-white/10 px-2 py-0.5">
            Iter {data.iteration}
          </span>
        ) : null}
        {data.function_name ? (
          <span className="rounded-full border border-white/10 px-2 py-0.5">
            {data.function_name}
          </span>
        ) : null}
      </div>
      <Handle type="source" position={Position.Bottom} className="!bg-white/80" />
    </div>
  );
};

export default ExecutionNode;
