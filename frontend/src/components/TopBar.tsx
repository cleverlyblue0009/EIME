import React from "react";
import { Cpu, Download, Play, Zap } from "lucide-react";

import { useDashboardStore } from "../store/useDashboardStore";
import StatusBadge from "./StatusBadge";

const TopBar: React.FC = () => {
  const analyze = useDashboardStore((state) => state.analyze);
  const simulate = useDashboardStore((state) => state.simulate);
  const isAnalyzing = useDashboardStore((state) => state.isAnalyzing);

  return (
    <div className="flex flex-wrap items-center justify-between gap-4 rounded-3xl border border-white/10 bg-gradient-to-r from-slate-900/80 to-slate-900/40 p-4 shadow-panel-md">
      <div className="flex items-center gap-3">
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-indigo-600/20 text-indigo-300">
          <Cpu size={24} />
        </div>
        <div>
          <p className="text-sm uppercase tracking-[0.3em] text-slate-400">ACRE / EIME</p>
          <h1 className="text-2xl font-semibold text-white">Intent Modeling Engine</h1>
        </div>
      </div>

      <div className="flex flex-1 flex-wrap items-center justify-end gap-3">
        <button
          onClick={analyze}
          className="flex items-center gap-2 rounded-2xl bg-white/10 px-4 py-2 text-sm font-semibold text-white transition hover:bg-white/20"
        >
          <Play size={14} />
          {isAnalyzing ? "Analyzing..." : "Analyze"}
        </button>
        <button
          onClick={simulate}
          className="flex items-center gap-2 rounded-2xl bg-indigo-600/80 px-4 py-2 text-sm font-semibold text-white transition hover:bg-indigo-500"
        >
          <Zap size={14} />
          Simulate
        </button>
        <button className="flex items-center gap-2 rounded-2xl border border-white/40 px-4 py-2 text-sm font-semibold text-white transition hover:border-white hover:bg-white/10">
          <Download size={14} />
          Export Report
        </button>
        <StatusBadge text="Session Active" tone="success" />
      </div>
    </div>
  );
};

export default TopBar;
