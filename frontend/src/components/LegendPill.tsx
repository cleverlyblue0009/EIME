import React from "react";

type LegendPillProps = {
  label: string;
  color: string;
};

const LegendPill: React.FC<LegendPillProps> = ({ label, color }) => {
  return (
    <span className={`flex items-center gap-2 rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.4em] ${color}`}>
      <span className="h-2 w-2 rounded-full bg-white" />
      {label}
    </span>
  );
};

export default LegendPill;
