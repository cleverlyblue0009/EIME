import React from "react";

import DivergenceCard from "./DivergenceCard";
import MetricCard from "./MetricCard";
import { useDashboardStore } from "../store/useDashboardStore";

const ReasoningPanel: React.FC = () => {
  const reasoning = useDashboardStore((state) => state.reasoning);
  const metrics = useDashboardStore((state) => state.metrics);
  const divergence = useDashboardStore((state) => state.divergence);

  const reasoningCards = [
    { title: "Intended Behavior", text: reasoning.intended },
    { title: "Actual Behavior", text: reasoning.actual },
    { title: "Divergence Detected", text: reasoning.divergence },
    { title: "Root Cause", text: reasoning.rootCause },
    { title: "Suggested Fix", text: reasoning.suggestedFix },
  ];

  return (
    <div className="flex flex-col gap-4">
      <div className="rounded-3xl border border-white/10 bg-slate-950/80 p-4 shadow-panel-md">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.4em] text-slate-500">AI Reasoning</p>
            <h2 className="text-2xl font-semibold text-white">Intent vs. Execution</h2>
          </div>
        </div>
        <div className="mt-4 space-y-3">
          {reasoningCards.map((card) => (
            <div key={card.title} className="rounded-2xl border border-white/5 bg-slate-900/60 p-3 text-sm text-slate-200">
              <p className="text-[10px] font-semibold uppercase tracking-[0.4em] text-slate-500">{card.title}</p>
              <p className="mt-2 text-sm leading-relaxed text-white/90">{card.text}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-3">
        <MetricCard title="Intent Confidence" value={metrics.intent_confidence} detail="Confidence predicted by intent engine" tone="positive" />
        <MetricCard title="Alignment Score" value={metrics.alignment_score} detail="Alignment between intent & execution" tone="neutral" />
        <MetricCard title="Divergence Severity" value={metrics.divergence_severity} detail="Real-time divergence evaluation" tone="caution" />
      </div>

      <DivergenceCard divergence={divergence} />
    </div>
  );
};

export default ReasoningPanel;
