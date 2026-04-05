import useIMEAnalysis from "../hooks/useIMEAnalysis";

const MetricsBar = () => {
  const { analysisResult } = useIMEAnalysis();
  const metrics = analysisResult?.metrics;

  return (
    <div className="metrics-bar">
      <div className="metric-chip">
        Algorithm: {metrics?.algorithm_detected || "—"}
      </div>
      <div className="metric-chip">
        Confidence: {metrics ? Math.round(metrics.intent_confidence * 100) : 0}%
      </div>
      <div className="metric-chip">
        Alignment: {metrics ? Math.round(metrics.alignment_score * 100) : 0}%
      </div>
      <div className="metric-chip">
        Invariants: {metrics?.invariant_violations ?? 0} violated
      </div>
      <div className="metric-chip">
        Divergences: {metrics?.divergence_count ?? 0}
      </div>
      <div className="metric-chip">
        Steps: {metrics?.execution_steps ?? 0}
      </div>
    </div>
  );
};

export default MetricsBar;
