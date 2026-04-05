import useIMEAnalysis from "../hooks/useIMEAnalysis";

const humanizeLabel = (value: string | null | undefined) => {
  if (!value) {
    return "Unknown";
  }
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
};

const formatStateValue = (value: any) => {
  if (typeof value === "string") {
    return value;
  }
  return JSON.stringify(value);
};

const renderStateBlock = (title: string, value: any) => {
  if (value === undefined || value === null || value === "" || (typeof value === "object" && Object.keys(value).length === 0)) {
    return null;
  }

  return (
    <div style={{ marginTop: 12 }}>
      <p style={{ margin: "0 0 6px", color: "var(--text-secondary)" }}>{title}</p>
      {typeof value === "object" && !Array.isArray(value) ? (
        <div style={{ display: "grid", gap: 6 }}>
          {Object.entries(value).map(([key, entry]) => (
            <div key={key} style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
              <span>{key}</span>
              <span style={{ color: "var(--text-secondary)", textAlign: "right" }}>{formatStateValue(entry)}</span>
            </div>
          ))}
        </div>
      ) : (
        <p style={{ margin: 0, color: "var(--text-secondary)" }}>{formatStateValue(value)}</p>
      )}
    </div>
  );
};

const ReasoningPanel = () => {
  const { analysisResult } = useIMEAnalysis();
  const reasoning = analysisResult?.reasoning;
  const intent = analysisResult?.intent_model;
  const topDivergence = analysisResult?.divergences?.[0];
  const invariantReport = analysisResult?.invariant_report ?? [];
  const metrics = analysisResult?.metrics;
  const structuralAlgorithm = intent?.inferred_algorithm || "Unknown";
  const geminiAlgorithm = reasoning?.llm_algorithm_guess || intent?.llm_advisory?.algorithm_type;
  const visibleVariant = !geminiAlgorithm || geminiAlgorithm === structuralAlgorithm ? intent?.algorithm_variant : null;
  const showDivergenceExplanation =
    reasoning?.divergence_explanation &&
    reasoning.divergence_explanation !==
      "No divergence explanation is needed because the observed behavior aligns with the inferred intent.";

  if (!analysisResult) {
    return (
      <div>
        <h3 style={{ margin: 0 }}>Reasoning</h3>
        <p style={{ color: "var(--text-secondary)" }}>
          Run analysis to see algorithm-level reasoning.
        </p>
      </div>
    );
  }

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h3 style={{ margin: 0 }}>Reasoning</h3>
        <span className="metric-chip">
          {humanizeLabel(geminiAlgorithm || structuralAlgorithm)}
          {visibleVariant ? ` - ${humanizeLabel(visibleVariant)}` : ""}
        </span>
      </div>
      {geminiAlgorithm && geminiAlgorithm !== structuralAlgorithm ? (
        <p style={{ margin: "8px 0 0", color: "var(--text-secondary)" }}>
          Gemini second pass classified this as {humanizeLabel(geminiAlgorithm)}. Structural first pass classified it as{" "}
          {humanizeLabel(structuralAlgorithm)}.
        </p>
      ) : null}
      <div style={{ marginTop: 8 }}>
        <p style={{ margin: 0, color: "var(--text-secondary)" }}>Confidence</p>
        <div
          style={{
            height: 8,
            borderRadius: 999,
            background: "#11141d",
            border: "1px solid var(--border)",
            overflow: "hidden",
            marginTop: 4,
          }}
        >
          <div
            style={{
              width: `${Math.round((reasoning?.confidence || 0) * 100)}%`,
              height: "100%",
              background: "var(--accent-blue)",
            }}
          />
        </div>
      </div>

      <div style={{ marginTop: 12 }}>
        <p>{reasoning?.executive_summary}</p>
      </div>

      {metrics ? (
        <div style={{ marginTop: 12, display: "flex", gap: 8, flexWrap: "wrap" }}>
          <span className="metric-chip">
            Exec alignment: {Math.round((metrics.execution_alignment_score ?? metrics.alignment_score ?? 0) * 100)}%
          </span>
          <span className="metric-chip">
            Invariant violations: {metrics.invariant_violations ?? 0}
          </span>
          <span className="metric-chip">
            Data-flow edges: {metrics.data_flow_edges ?? 0}
          </span>
        </div>
      ) : null}

      {showDivergenceExplanation ? (
        <div style={{ marginTop: 12 }}>
          <p style={{ margin: "0 0 6px", color: "var(--text-secondary)" }}>What went wrong</p>
          <p style={{ margin: 0 }}>{reasoning.divergence_explanation}</p>
        </div>
      ) : null}

      {topDivergence ? (
        <div style={{ marginTop: 12 }}>
          <p style={{ margin: "0 0 6px", color: "var(--text-secondary)" }}>First Divergence</p>
          <div className="metric-chip">
            {humanizeLabel(topDivergence.type)} at{" "}
            {topDivergence.divergence_point || `line ${topDivergence.first_occurrence_line}`}
          </div>
          {renderStateBlock("Expected State", topDivergence.expected_state)}
          {renderStateBlock("Actual State", topDivergence.actual_state)}
          {renderStateBlock("Missing State", topDivergence.missing_state)}
        </div>
      ) : null}

      {invariantReport.length ? (
        <details style={{ marginTop: 12 }}>
          <summary>Invariant report</summary>
          <div style={{ display: "grid", gap: 10, marginTop: 8 }}>
            {invariantReport.slice(0, 6).map((item: any) => (
              <div key={item.invariant} style={{ borderTop: "1px solid var(--border)", paddingTop: 8 }}>
                <p style={{ margin: 0 }}>{item.invariant}</p>
                <p style={{ margin: "4px 0 0", color: "var(--text-secondary)" }}>
                  Expected: {item.expected_condition}
                </p>
                <p style={{ margin: "4px 0 0", color: "var(--text-secondary)" }}>
                  Observed: {item.observed_condition}
                </p>
                <p style={{ margin: "4px 0 0", color: item.violation ? "#fda4af" : "var(--text-secondary)" }}>
                  {item.violation ? "Violation detected" : "No violation detected"}
                </p>
              </div>
            ))}
          </div>
        </details>
      ) : null}

      <details>
        <summary>Intended behavior</summary>
        <p>{reasoning?.intended_behavior}</p>
      </details>
      <details>
        <summary>Actual behavior</summary>
        <p>{reasoning?.actual_behavior}</p>
      </details>
      <details>
        <summary>Root cause</summary>
        <p>{reasoning?.root_cause}</p>
      </details>
      <details open>
        <summary>Fix suggestion</summary>
        <p>{reasoning?.fix_suggestion}</p>
      </details>
      {reasoning?.llm_summary ? (
        <details>
          <summary>Gemini Reasoning</summary>
          <p>{reasoning.llm_summary}</p>
          {reasoning.llm_algorithm_guess ? (
            <p style={{ color: "var(--text-secondary)" }}>
              Gemini classification: {humanizeLabel(reasoning.llm_algorithm_guess)}
            </p>
          ) : null}
          {reasoning.deeper_bug_hypotheses?.length ? (
            <ul style={{ paddingLeft: 16, margin: 0 }}>
              {reasoning.deeper_bug_hypotheses.map((item: string) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          ) : null}
        </details>
      ) : null}
      {reasoning?.deterministic_boundary ? (
        <p style={{ marginTop: 12, color: "var(--text-secondary)", fontSize: 12 }}>
          {reasoning.deterministic_boundary}
        </p>
      ) : null}
    </div>
  );
};

export default ReasoningPanel;
