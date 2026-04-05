import { useState } from "react";
import useIMEAnalysis from "../hooks/useIMEAnalysis";

const SimulationControls = () => {
  const { analysisResult, simulate, graphNodes, selectedNodeId } = useIMEAnalysis();
  const [variable, setVariable] = useState("");
  const [value, setValue] = useState("");
  const [loopId, setLoopId] = useState("");
  const [loopBound, setLoopBound] = useState("");
  const [conditionLine, setConditionLine] = useState("");
  const [conditionExpr, setConditionExpr] = useState("");
  const selectedNode = graphNodes.find((node: any) => node.id === selectedNodeId);
  const selectedLine = selectedNode?.data?.detail?.code_ref?.lineno;
  const selectedSnapshot = selectedNode?.data?.detail?.variable_snapshot || {};
  const editableFields = selectedNode?.data?.detail?.editable_fields || Object.keys(selectedSnapshot);

  if (!analysisResult) {
    return null;
  }

  const onApplyVariable = () => {
    simulate({
      analysis_id: analysisResult.analysis_id,
      patch_type: "variable_override",
      target_line: selectedLine,
      target_variable: variable,
      new_value: value,
    });
  };

  const onApplyLoop = () => {
    simulate({
      analysis_id: analysisResult.analysis_id,
      patch_type: "loop_bound_override",
      target_line: Number(loopId || selectedLine),
      new_value: loopBound,
    });
  };

  const onApplyCondition = () => {
    simulate({
      analysis_id: analysisResult.analysis_id,
      patch_type: "condition_override",
      target_line: Number(conditionLine || selectedLine),
      new_value: conditionExpr,
    });
  };

  return (
    <div style={{ marginTop: 16 }}>
      <h3>Simulation Controls</h3>
      {selectedLine ? (
        <p style={{ margin: "6px 0 12px", color: "var(--text-secondary)" }}>
          Active target line: {selectedLine}
        </p>
      ) : (
        <p style={{ margin: "6px 0 12px", color: "var(--text-secondary)" }}>
          Select a node to anchor overrides to a specific execution step.
        </p>
      )}
      <div style={{ display: "grid", gap: 8 }}>
        <div>
          <p style={{ margin: 0, color: "var(--text-secondary)" }}>Variable override</p>
          {editableFields.length ? (
            <select
              value={variable}
              onChange={(e) => setVariable(e.target.value)}
              style={{ width: "100%", marginBottom: 6 }}
            >
              <option value="">select variable from node</option>
              {editableFields.map((field: string) => (
                <option key={field} value={field}>
                  {field}
                </option>
              ))}
            </select>
          ) : null}
          <input
            value={variable}
            onChange={(e) => setVariable(e.target.value)}
            placeholder="variable name"
            style={{ width: "100%", marginBottom: 6 }}
          />
          <input
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder="new value"
            style={{ width: "100%", marginBottom: 6 }}
          />
          {variable && variable in selectedSnapshot ? (
            <p style={{ margin: "0 0 6px", color: "var(--text-secondary)" }}>
              Current value: {JSON.stringify(selectedSnapshot[variable])}
            </p>
          ) : null}
          <button className="button-secondary" onClick={onApplyVariable}>
            Re-run With Variable Override
          </button>
        </div>
        <div>
          <p style={{ margin: 0, color: "var(--text-secondary)" }}>Loop bound override</p>
          <input
            value={loopId}
            onChange={(e) => setLoopId(e.target.value)}
            placeholder={selectedLine ? `loop header line (default ${selectedLine})` : "loop header line"}
            style={{ width: "100%", marginBottom: 6 }}
          />
          <input
            value={loopBound}
            onChange={(e) => setLoopBound(e.target.value)}
            placeholder="new bound"
            style={{ width: "100%", marginBottom: 6 }}
          />
          <button className="button-secondary" onClick={onApplyLoop}>
            Re-run With Loop Override
          </button>
        </div>
        <div>
          <p style={{ margin: 0, color: "var(--text-secondary)" }}>Condition override</p>
          <input
            value={conditionLine}
            onChange={(e) => setConditionLine(e.target.value)}
            placeholder={selectedLine ? `condition line (default ${selectedLine})` : "condition line"}
            style={{ width: "100%", marginBottom: 6 }}
          />
          <input
            value={conditionExpr}
            onChange={(e) => setConditionExpr(e.target.value)}
            placeholder="new condition expression"
            style={{ width: "100%", marginBottom: 6 }}
          />
          <button className="button-secondary" onClick={onApplyCondition}>
            Re-run With Condition Override
          </button>
        </div>
      </div>
    </div>
  );
};

export default SimulationControls;
