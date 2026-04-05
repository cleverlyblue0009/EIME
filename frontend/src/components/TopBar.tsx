import React from "react";
import { Cpu, Download, Play, Sparkles } from "lucide-react";

import { useDashboardStore } from "../store/useDashboardStore";
import { buildExecutionGraph, buildExecutionGraphFromBackend } from "../utils/graphBuilder";
import { layoutGraph } from "../utils/graphLayout";
import { downloadJsonFile } from "../utils/download";
import StatusBadge from "./StatusBadge";

const TopBar: React.FC = () => {
  const analyze = useDashboardStore((state) => state.analyze);
  const isAnalyzing = useDashboardStore((state) => state.isAnalyzing);
  const apiError = useDashboardStore((state) => state.apiError);
  const code = useDashboardStore((state) => state.code);
  const executionTrace = useDashboardStore((state) => state.executionTrace);
  const intentTrace = useDashboardStore((state) => state.intentTrace);
  const divergence = useDashboardStore((state) => state.divergence);
  const backendGraph = useDashboardStore((state) => state.graph);
  const metrics = useDashboardStore((state) => state.metrics);
  const timeline = useDashboardStore((state) => state.timeline);

  const handleExport = () => {
    const graphResult =
      (backendGraph?.nodes?.length ?? 0) > 0
        ? buildExecutionGraphFromBackend(backendGraph, code)
        : buildExecutionGraph(executionTrace, intentTrace, divergence, code);
    const layoutedNodes = layoutGraph(graphResult.nodes, graphResult.edges, {
      direction: "TB",
      rankSep: 110,
      nodeSep: 70,
    });
    const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
    const payload = {
      generated_at: new Date().toISOString(),
      code,
      metadata: {
        total_steps: executionTrace.length,
        divergence,
        metrics,
        timeline,
      },
      graph: {
        nodes: layoutedNodes,
        edges: graphResult.edges,
      },
    };
    downloadJsonFile(`eime-graph-${timestamp}.json`, payload);
  };

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

      {apiError ? (
        <div className="w-full rounded-2xl border border-red-400/50 bg-red-500/15 px-3 py-2 text-sm text-red-300">
          <strong>Error:</strong> {apiError}
        </div>
      ) : null}

      <div className="flex flex-1 flex-wrap items-center justify-end gap-3">
        <button
          onClick={analyze}
          className="flex items-center gap-2 rounded-2xl bg-white/10 px-4 py-2 text-sm font-semibold text-white transition hover:bg-white/20"
        >
          <Play size={14} />
          {isAnalyzing ? "Analyzing..." : "Analyze"}
        </button>
        <div className="flex items-center gap-2 rounded-2xl border border-emerald-400/30 bg-emerald-500/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.3em] text-emerald-200">
          <Sparkles size={14} />
          Live Sync
        </div>
        <button
          onClick={handleExport}
          className="flex items-center gap-2 rounded-2xl border border-white/40 px-4 py-2 text-sm font-semibold text-white transition hover:border-white hover:bg-white/10"
        >
          <Download size={14} />
          Export Graph
        </button>
        <StatusBadge text="Session Active" tone="success" />
      </div>
    </div>
  );
};

export default TopBar;
