import useIMEAnalysis from "../hooks/useIMEAnalysis";

const humanizeLabel = (value: string | null | undefined) => {
  if (!value) {
    return "";
  }
  return value.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
};

const formatValue = (value: any) => {
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
      <h4>{title}</h4>
      {typeof value === "object" && !Array.isArray(value) ? (
        <div style={{ display: "grid", gap: 6 }}>
          {Object.entries(value).map(([key, entry]) => (
            <div key={key} style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
              <span>{key}</span>
              <span style={{ color: "var(--text-secondary)", textAlign: "right" }}>{formatValue(entry)}</span>
            </div>
          ))}
        </div>
      ) : (
        <p style={{ margin: 0, color: "var(--text-secondary)" }}>{formatValue(value)}</p>
      )}
    </div>
  );
};

const NodeInspector = () => {
  const { selectedNodeId, graphNodes, analysisResult } = useIMEAnalysis();
  const node = graphNodes.find((n: any) => n.id === selectedNodeId);

  if (!node) {
    return (
      <div style={{ marginTop: 16 }}>
        <h3 style={{ margin: 0 }}>Node Inspector</h3>
        <p style={{ color: "var(--text-secondary)" }}>
          Select a node in the graph to inspect full state, operation, and causal context.
        </p>
      </div>
    );
  }

  const detail = node.data?.detail || {};
  const snapshot = detail.variable_snapshot || {};
  const variableDeltas = detail.variable_deltas || {};
  const rawNode = node.data?.raw;
  const divergence =
    rawNode?.type === "divergence"
      ? analysisResult?.divergences?.find(
          (d: any) =>
            d.type === detail.role_in_algorithm ||
            d.actual_behavior === detail.full_description ||
            d.symptom_line === detail.code_ref?.lineno
        )
      : null;
  const detectionSource = divergence?.evidence?.source === "LLM_SECOND_PASS" ? "Gemini second pass" : divergence ? "Deterministic rule engine" : null;

  return (
    <div style={{ marginTop: 16 }}>
      <h3 style={{ marginBottom: 8 }}>Node Inspector</h3>
      <div className="metric-chip">{node.data?.label}</div>
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginTop: 8, color: "var(--text-secondary)" }}>
        {detail.step ? <span>Step {detail.step}</span> : null}
        {detail.operation ? <span>Operation: {detail.operation}</span> : null}
        {detail.code_ref?.lineno ? <span>Line {detail.code_ref.lineno}</span> : null}
        {detail.function_context ? <span>Function: {detail.function_context}</span> : null}
        {detail.iteration_index ? <span>Iteration: {detail.iteration_index}</span> : null}
        {detail.scope_event ? <span>Scope: {detail.scope_event}</span> : null}
        {detail.scope_depth ? <span>Depth: {detail.scope_depth}</span> : null}
      </div>

      {detail.code_line ? (
        <div style={{ marginTop: 12 }}>
          <h4>Code</h4>
          <pre style={{ margin: 0, whiteSpace: "pre-wrap", color: "var(--text-secondary)" }}>
            {detail.code_line}
          </pre>
        </div>
      ) : null}

      <div style={{ marginTop: 12 }}>
        <h4>Explanation</h4>
        <p style={{ color: "var(--text-secondary)" }}>{detail.full_description}</p>
      </div>

      <div>
        <h4>Role in Algorithm</h4>
        <p style={{ color: "var(--text-secondary)" }}>{humanizeLabel(detail.role_in_algorithm)}</p>
      </div>

      <div>
        <h4>Why This Matters</h4>
        <p style={{ color: "var(--text-secondary)" }}>{detail.why_matters}</p>
      </div>

      {detectionSource ? (
        <div>
          <h4>Detection Source</h4>
          <p style={{ color: "var(--text-secondary)" }}>{detectionSource}</p>
        </div>
      ) : null}

      <div>
        <h4>Variable Snapshot</h4>
        <div>
          {Object.keys(snapshot).length === 0 ? (
            <p style={{ color: "var(--text-secondary)" }}>No variables captured.</p>
          ) : (
            Object.entries(snapshot).map(([key, value]) => (
              <div key={key} style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                <span>{key}</span>
                <span style={{ color: "var(--text-secondary)", textAlign: "right" }}>
                  {JSON.stringify(value)}
                </span>
              </div>
            ))
          )}
        </div>
      </div>

      {Object.keys(variableDeltas).length ? (
        <div style={{ marginTop: 12 }}>
          <h4>Changed Variables</h4>
          <div style={{ display: "grid", gap: 6 }}>
            {Object.entries(variableDeltas).map(([name, delta]: [string, any]) => (
              <div key={name} style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                <span>{name}</span>
                <span style={{ color: "var(--text-secondary)", textAlign: "right" }}>
                  {formatValue(delta?.from)} {"->"} {formatValue(delta?.to)}
                </span>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {detail.data_dependencies?.length ? (
        <div style={{ marginTop: 12 }}>
          <h4>Data Dependencies</h4>
          <p style={{ color: "var(--text-secondary)" }}>{detail.data_dependencies.join(", ")}</p>
        </div>
      ) : null}

      {detail.alignment_targets?.length ? (
        <div style={{ marginTop: 12 }}>
          <h4>Alignment Targets</h4>
          <p style={{ color: "var(--text-secondary)" }}>
            {detail.alignment_targets.map((target: string) => humanizeLabel(target)).join(", ")}
          </p>
        </div>
      ) : null}

      {detail.editable_fields?.length ? (
        <div style={{ marginTop: 12 }}>
          <h4>Editable Fields</h4>
          <p style={{ color: "var(--text-secondary)" }}>
            {detail.editable_fields.slice(0, 8).join(", ")}
          </p>
        </div>
      ) : null}

      <div style={{ marginTop: 12 }}>
        <h4>Invariants Checked</h4>
        <ul style={{ paddingLeft: 16, margin: 0 }}>
          {(detail.invariants_checked || []).map((inv: string) => (
            <li key={inv}>{inv}</li>
          ))}
        </ul>
      </div>

      {renderStateBlock("Expected State", detail.expected_state || divergence?.expected_state)}
      {renderStateBlock("Actual State", detail.actual_state || divergence?.actual_state)}
      {renderStateBlock("Missing State", detail.missing_state || divergence?.missing_state)}
      {renderStateBlock("Extra State", detail.extra_state || divergence?.extra_state)}

      {((detail.causal_chain && detail.causal_chain.length > 0) || (divergence?.causal_chain && divergence.causal_chain.length > 0)) ? (
        <div style={{ marginTop: 12 }}>
          <h4>Causal Chain</h4>
          <ul style={{ paddingLeft: 16, margin: 0 }}>
            {(detail.causal_chain?.length ? detail.causal_chain : divergence?.causal_chain || []).map((step: any, index: number) => (
              <li key={`${step.step_index ?? step.lineno ?? index}`}>
                {step.description} {step.lineno ? `(line ${step.lineno})` : ""}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {divergence ? (
        <div style={{ marginTop: 12 }}>
          <h4>Suggested Fix</h4>
          <p style={{ color: "var(--text-secondary)" }}>{divergence.fix_suggestion}</p>
        </div>
      ) : null}
    </div>
  );
};

export default NodeInspector;
