import React from "react";

type DivergenceCardProps = {
  divergence: {
    first_divergence: string;
    score: number;
    severity: string;
    causal_chain: Array<string | { line?: number; reason?: string }>;
  };
};

const DivergenceCard: React.FC<DivergenceCardProps> = ({ divergence }) => {
  if (!divergence || !Array.isArray(divergence.causal_chain)) {
    return (
      <div className="rounded-3xl border border-red-500/40 bg-slate-950/80 p-4 shadow-lg ring-1 ring-red-500/30 text-slate-300">
        No divergence data available.
      </div>
    );
  }

  const formatCausalChainItem = (item: string | { line?: number; reason?: string }) => {
    if (typeof item === "string") {
      return item;
    }
    if (typeof item === "object" && item) {
      const parts = [];
      if (item.line !== undefined && item.line !== null) {
        parts.push(`Line ${item.line}`);
      }
      if (item.reason) {
        parts.push(item.reason);
      }
      return parts.length > 0 ? parts.join(": ") : "Unknown cause";
    }
    return String(item);
  };

  return (
    <div className="rounded-3xl border border-red-500/40 bg-gradient-to-br from-slate-900/90 via-slate-950/70 to-black/60 p-4 shadow-xl ring-1 ring-red-500/30">
      <div className="flex items-center justify-between">
        <p className="text-xs font-bold uppercase tracking-[0.4em] text-red-300">Divergence Detected</p>
        <span className="rounded-full border border-red-400/40 bg-red-500/15 px-3 py-1 text-[11px] font-semibold text-red-100">
          {divergence.severity || "UNKNOWN"}
        </span>
      </div>
      <p className="mt-3 text-lg font-bold text-white">
        {divergence.first_divergence || "No divergence found"}
      </p>
      <p className="text-xs text-red-200">Score {divergence.score ?? 0}</p>
      <ul className="mt-3 space-y-2 text-sm text-slate-300">
        {(divergence.causal_chain ?? []).map((item, idx) => (
          <li key={`${idx}-${typeof item === "string" ? item : item?.reason}`} className="flex items-start gap-2">
            <span className="mt-1 h-2 w-2 rounded-full bg-red-400" />
            <span>{formatCausalChainItem(item)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
};

export default DivergenceCard;
