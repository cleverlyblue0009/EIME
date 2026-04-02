import React from "react";

type MetricCardProps = {
  title: string;
  value: string;
  detail?: string;
  tone?: "neutral" | "positive" | "caution";
};

const toneClasses: Record<string, string> = {
  neutral: "bg-slate-900/50 text-white border border-white/10",
  positive: "bg-emerald-500/5 text-emerald-200 border border-emerald-500/40",
  caution: "bg-amber-500/5 text-amber-200 border border-amber-500/40",
};

const MetricCard: React.FC<MetricCardProps> = ({ title, value, detail, tone = "neutral" }) => (
  <div className={`w-full rounded-2xl px-4 py-3 text-sm font-semibold tracking-wide ${toneClasses[tone]}`}>
    <p className="text-[10px] uppercase text-white/50">{title}</p>
    <p className="text-2xl text-white">{value}</p>
    {detail && <p className="text-xs text-white/60">{detail}</p>}
  </div>
);

export default MetricCard;
