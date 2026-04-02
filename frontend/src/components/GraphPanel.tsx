import React from "react";
import { motion } from "framer-motion";
import { Eye, Move, SlidersHorizontal } from "lucide-react";

import { useDashboardStore } from "../store/useDashboardStore";
import LegendPill from "./LegendPill";

const nodePositions: Record<string, { left: string; top: string }> = {
  "node-start": { left: "5%", top: "70%" },
  "node-intended": { left: "35%", top: "25%" },
  "node-actual": { left: "65%", top: "45%" },
  "node-exec-6": { left: "65%", top: "75%" },
};

const GraphPanel: React.FC = () => {
  const graph = useDashboardStore((state) => state.graph);
  const timeline = useDashboardStore((state) => state.timeline);

  return (
    <div className="flex flex-col rounded-3xl border border-white/10 bg-slate-950/60 p-4 shadow-panel-md">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.4em] text-slate-500">Intent · Execution Graph</p>
          <h2 className="text-2xl font-semibold text-white">Visual Dual Execution</h2>
        </div>
        <div className="flex items-center gap-3 text-xs text-slate-400">
          <button className="flex items-center gap-1 rounded-full border border-white/10 px-3 py-1 transition hover:border-white">
            <Eye size={14} />
            Zoom
          </button>
          <button className="flex items-center gap-1 rounded-full border border-white/10 px-3 py-1 transition hover:border-white">
            <Move size={14} />
            Pan
          </button>
        </div>
      </div>

      <div className="mt-4 flex flex-col gap-4">
        <div className="flex gap-2">
          <LegendPill label="Intended" color="bg-intent/10 text-intent border border-intent/40" />
          <LegendPill label="Actual" color="bg-blue-500/10 text-blue-300 border border-blue-500/30" />
          <LegendPill label="Divergence" color="bg-red-500/10 text-red-300 border border-red-500/40" />
        </div>

        <div className="relative h-[440px] w-full overflow-hidden rounded-2xl border border-white/5 bg-gradient-to-br from-slate-900 via-slate-950 to-slate-900/70">
          {graph.nodes.map((node) => {
            const position = nodePositions[node.id] || { left: "50%", top: "50%" };
            const baseColor = node.type === "divergence" ? "bg-red-500/80" : node.type === "intended" ? "bg-emerald-500/70" : node.type === "actual" ? "bg-blue-500/70" : "bg-white/10";
            return (
              <motion.div
                key={node.id}
                style={{ left: position.left, top: position.top }}
                initial={{ scale: 0.9 }}
                animate={node.type === "divergence" ? { scale: [0.9, 1.1, 0.95], boxShadow: "0 0 25px rgba(248, 113, 113, 0.9)" } : { scale: 1 }}
                transition={{ duration: 1.6, repeat: node.type === "divergence" ? Infinity : 0 }}
                className={`absolute flex w-36 flex-col rounded-2xl border border-white/10 p-3 text-xs font-semibold uppercase tracking-[0.4em] text-white ${baseColor}`}
              >
                <span className="text-[10px] text-white/60">{node.type}</span>
                <span className="text-sm">{node.label}</span>
                {node.id === graph.first_divergence && (
                  <span className="mt-2 text-[10px] text-red-200">FIRST DIVERGENCE</span>
                )}
              </motion.div>
            );
          })}
        </div>
      </div>

      <div className="mt-4 flex items-center justify-between rounded-2xl border border-white/5 bg-slate-900/60 px-4 py-3">
        <div>
          <p className="text-xs uppercase tracking-[0.3em] text-slate-400">Timeline</p>
          <p className="text-sm text-white">
            t = {timeline.latency} · Frame {timeline.frame}
          </p>
        </div>
        <div className="flex items-center gap-3 text-xs text-slate-400">
          <SlidersHorizontal size={16} />
          <div className="flex items-center gap-1 rounded-full border border-white/20 px-3 py-1 text-[11px]">
            {timeline.progress}% loaded
          </div>
        </div>
      </div>
    </div>
  );
};

export default GraphPanel;
