import React from "react";

type StatusBadgeProps = {
  text: string;
  tone?: "success" | "warning" | "neutral";
};

const toneStyles: Record<string, string> = {
  success: "bg-emerald-500/10 text-emerald-300 border border-emerald-500/60",
  warning: "bg-amber-500/10 text-amber-300 border border-amber-500/60",
  neutral: "bg-slate-500/10 text-slate-200 border border-slate-500/40",
};

const StatusBadge: React.FC<StatusBadgeProps> = ({ text, tone = "success" }) => {
  return (
    <span className={`inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium ${toneStyles[tone]}`}>
      <span className={`h-2 w-2 rounded-full ${tone === "warning" ? "bg-amber-300" : tone === "neutral" ? "bg-slate-300" : "bg-emerald-300"}`} />
      {text}
    </span>
  );
};

export default StatusBadge;
