import React from "react";

type DivergenceCardProps = {
  divergence: {
    first_divergence: string;
    score: number;
    severity: string;
    causal_chain: string[];
  };
};

const DivergenceCard: React.FC<DivergenceCardProps> = ({ divergence }) => {
  return (
    <div className="rounded-3xl border border-red-500/40 bg-black/40 p-4 shadow-panel-md">
      <div className="flex items-center justify-between">
        <p className="text-xs font-semibold uppercase tracking-[0.4em] text-red-300">Divergence Detected</p>
        <span className="rounded-full border border-red-500/40 bg-red-500/10 px-3 py-1 text-[11px] font-semibold text-red-200">
          {divergence.severity}
        </span>
      </div>
      <p className="mt-3 text-lg font-semibold text-white">
        {divergence.first_divergence} <span className="text-xs text-red-300">(score {divergence.score})</span>
      </p>
      <ul className="mt-2 space-y-1 text-sm text-slate-300">
        {divergence.causal_chain.map((item) => (
          <li key={item} className="flex items-start gap-2">
            <span className="mt-1 h-1 w-1 rounded-full bg-red-400" />
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
};

export default DivergenceCard;
