from __future__ import annotations

import uuid
from typing import Any, Dict, List, Tuple

from backend.api.models import AnalysisResponse, CognitivePrior, Metrics
from backend.alignment.alignment_engine import AlignmentEngine
from backend.execution.sandbox import execute_with_trace
from backend.normalizer.trace_normalizer import normalize_trace
from backend.intent.intent_engine import IntentEngine
from backend.expectation.expectation_generator import ExpectationGenerator
from backend.divergence.divergence_engine import DivergenceEngine
from backend.fingerprint.fingerprint_engine import FingerprintEngine
from backend.fingerprint.fingerprint_store import FingerprintStore
from backend.graph.graph_engine import build as build_graph
from backend.graph.graph_views import build_data_flow_view, build_execution_view
from backend.graph.intent_graph import build_intent_graph
from backend.graph.graph_layout import apply_layout
from backend.invariants.invariant_engine import InvariantEngine
from backend.reasoning.reasoning_engine import collect_llm_reasoning, generate as generate_reasoning
from backend.reasoning.semantic_divergence import build_semantic_divergences
from backend.parser.ast_parser import (
    parse_code,
    collect_imports,
    collect_var_names,
    collect_loops,
    build_line_index,
)
from backend.parser.cfg_builder import build_cfg
from backend.parser.vdg_builder import build_vdg
from backend.parser.call_graph_builder import build_call_graph


intent_engine = IntentEngine()
expectation_generator = ExpectationGenerator()
divergence_engine = DivergenceEngine()
invariant_engine = InvariantEngine()
alignment_engine = AlignmentEngine()
fingerprint_store = FingerprintStore()
fingerprint_engine = FingerprintEngine(fingerprint_store)


def build_parse_result(code: str) -> Dict[str, Any]:
    result = parse_code(code)
    tree = result.get("ast")
    if tree:
        imports = collect_imports(tree)
        var_names = collect_var_names(tree)
        loops = collect_loops(tree)
        line_index = build_line_index(tree, code)
        cfg = build_cfg(tree)
        vdg = build_vdg(tree)
        call_graph = build_call_graph(tree)
    else:
        imports = []
        var_names = set()
        loops = []
        line_index = {}
        cfg = {}
        vdg = {}
        call_graph = {}

    cfg["source"] = code

    return {
        "ast": tree,
        "source": code,
        "imports": imports,
        "var_names": var_names,
        "loops": loops,
        "line_index": line_index,
        "cfg": cfg,
        "vdg": vdg,
        "call_graph": call_graph,
        "line_count": len(code.splitlines()),
    }


def run_analysis(
    code: str,
    stdin_input: str = "",
    gemini_api_key: str | None = None,
    user_id: str | None = None,
) -> AnalysisResponse:
    analysis_id = str(uuid.uuid4())
    normalized_user_id = user_id.strip() if isinstance(user_id, str) else None
    if not normalized_user_id:
        normalized_user_id = None

    parse_result = build_parse_result(code)
    execution = execute_with_trace(code, stdin_input)
    normalized_trace = normalize_trace(execution["trace"], parse_result)

    fingerprint: Dict[str, Any] = {}
    prior: Dict[str, Any] = {}
    if normalized_user_id:
        try:
            fingerprint = fingerprint_store.load(normalized_user_id)
            prior = fingerprint_engine.build_prior(fingerprint)
        except Exception:
            fingerprint = {}
            prior = {}

    intent_model = intent_engine.analyze(parse_result, normalized_trace)
    if normalized_user_id and prior:
        try:
            blindspot_lines = fingerprint_engine.predict_blindspot_lines(
                fingerprint,
                parse_result,
                intent_model,
            )
            prior["blind_spot_lines"] = blindspot_lines
        except Exception:
            prior["blind_spot_lines"] = []
    expectation_model = expectation_generator.generate(intent_model, normalized_trace, parse_result)
    divergences = divergence_engine.detect(normalized_trace, intent_model, expectation_model, parse_result)
    llm_result = collect_llm_reasoning(
        divergences,
        intent_model,
        normalized_trace,
        code=code,
        gemini_api_key=gemini_api_key,
        cognitive_addendum=prior.get("prompt_addendum", ""),
    )
    semantic_divergences = build_semantic_divergences(llm_result, normalized_trace, intent_model, parse_result, divergences)
    divergences = divergence_engine.finalize(divergences + semantic_divergences, normalized_trace, intent_model, expectation_model)
    invariant_report = invariant_engine.analyze(normalized_trace, intent_model, expectation_model, parse_result, divergences)
    intent_steps, alignment_map = alignment_engine.build(normalized_trace, intent_model, divergences)
    reasoning = generate_reasoning(
        divergences,
        intent_model,
        normalized_trace,
        llm_result=llm_result,
    )
    _attach_reasoning_advisory(intent_model, reasoning, llm_result)
    graph = apply_layout(build_graph(normalized_trace, intent_model, divergences, parse_result))
    _attach_alignment_targets(graph, alignment_map)
    execution_graph = apply_layout(build_execution_view(graph))
    data_flow_graph = apply_layout(build_data_flow_view(graph))
    intent_graph = apply_layout(build_intent_graph(intent_model, intent_steps, alignment_map))

    metrics = _build_metrics(
        intent_model,
        normalized_trace,
        reasoning,
        divergences,
        invariant_report,
        alignment_map,
        data_flow_graph,
        intent_steps,
    )

    response = AnalysisResponse(
        analysis_id=analysis_id,
        normalized_trace=normalized_trace,
        intent_model=intent_model,
        expectation_model=expectation_model,
        divergences=divergences,
        graph=graph,
        execution_graph=execution_graph,
        intent_graph=intent_graph,
        data_flow_graph=data_flow_graph,
        alignment_map=[entry.model_dump() for entry in alignment_map],
        invariant_report=[item.model_dump() for item in invariant_report],
        divergence_report=_divergence_report(divergences),
        reasoning=reasoning,
        metrics=metrics,
        execution_trace=[_execution_step_payload(step) for step in normalized_trace.steps],
        intent=intent_model.model_dump(),
        divergence=_divergence_summary(divergences),
    )
    if normalized_user_id:
        try:
            updated_fingerprint = fingerprint_store.update(normalized_user_id, response)
            if updated_fingerprint:
                response.cognitive_prior = CognitivePrior(
                    user_id=normalized_user_id,
                    session_count=updated_fingerprint["session_count"],
                    dominant_error_class=updated_fingerprint.get("dominant_error_class"),
                    algorithm_blindspots=updated_fingerprint.get("algorithm_blindspots", []),
                    cognitive_traits=updated_fingerprint.get("cognitive_traits", {}),
                    predicted_blindspot_lines=prior.get("blind_spot_lines", []),
                    prompt_addendum=prior.get("prompt_addendum", ""),
                )
        except Exception:
            pass
    return response


def run_analysis_staged(code: str, stdin_input: str = "", gemini_api_key: str | None = None) -> List[Tuple[str, Any]]:
    stages: List[Tuple[str, Any]] = []

    parse_result = build_parse_result(code)
    stages.append(
        (
            "parser",
            {
                "imports": parse_result["imports"],
                "var_names": sorted(parse_result["var_names"]),
                "loops": parse_result["loops"],
                "line_count": parse_result["line_count"],
            },
        )
    )

    execution = execute_with_trace(code, stdin_input)
    stages.append(("execution", {"trace": [e.model_dump() for e in execution["trace"]], "output": execution["output"], "error": execution["error"]}))

    normalized_trace = normalize_trace(execution["trace"], parse_result)
    stages.append(("normalizer", normalized_trace.model_dump()))

    intent_model = intent_engine.analyze(parse_result, normalized_trace)
    stages.append(("intent", intent_model.model_dump()))

    expectation_model = expectation_generator.generate(intent_model, normalized_trace, parse_result)
    stages.append(("expectation", expectation_model.model_dump()))

    divergences = divergence_engine.detect(normalized_trace, intent_model, expectation_model, parse_result)
    llm_result = collect_llm_reasoning(
        divergences,
        intent_model,
        normalized_trace,
        code=code,
        gemini_api_key=gemini_api_key,
    )
    semantic_divergences = build_semantic_divergences(llm_result, normalized_trace, intent_model, parse_result, divergences)
    divergences = divergence_engine.finalize(divergences + semantic_divergences, normalized_trace, intent_model, expectation_model)
    stages.append(("divergence", [d.model_dump() for d in divergences]))
    invariant_report = invariant_engine.analyze(normalized_trace, intent_model, expectation_model, parse_result, divergences)
    stages.append(("invariants", [item.model_dump() for item in invariant_report]))
    intent_steps, alignment_map = alignment_engine.build(normalized_trace, intent_model, divergences)
    stages.append(("alignment", [item.model_dump() for item in alignment_map]))

    reasoning = generate_reasoning(
        divergences,
        intent_model,
        normalized_trace,
        llm_result=llm_result,
    )
    _attach_reasoning_advisory(intent_model, reasoning, llm_result)
    stages.append(("reasoning", reasoning.model_dump()))

    graph = apply_layout(build_graph(normalized_trace, intent_model, divergences, parse_result))
    _attach_alignment_targets(graph, alignment_map)
    stages.append(("graph", graph))
    stages.append(("execution_graph", apply_layout(build_execution_view(graph))))
    stages.append(("data_flow_graph", apply_layout(build_data_flow_view(graph))))
    stages.append(("intent_graph", apply_layout(build_intent_graph(intent_model, intent_steps, alignment_map))))

    return stages


def _execution_step_payload(step) -> Dict[str, Any]:
    return {
        "step_id": step.step_id,
        "line_number": step.lineno,
        "code_snippet": step.code_snippet or step.code_line,
        "variables": step.variables or step.variable_snapshot,
        "full_state": step.variable_snapshot,
        "diff_state": step.variable_deltas,
        "operation_type": step.operation_type or step.operation,
        "iteration_index": step.iteration_index,
        "function_context": step.function_context,
        "parent_step": step.parent_step_id,
        "timestamp_ns": getattr(step, "timestamp_ns", None),
        "scope_depth": getattr(step, "scope_depth", 0),
        "scope_event": getattr(step, "scope_event", None),
        "description": step.description,
        "data_dependencies": list(step.data_dependencies or step.read_accesses),
    }


def _divergence_summary(divergences) -> Dict[str, Any]:
    if not divergences:
        return {}
    top = divergences[0]
    return {
        "type": top.type,
        "line": top.first_occurrence_line,
        "explanation": top.explanation or top.actual_behavior,
        "expected_state": top.expected_state,
        "actual_state": top.actual_state,
        "root_cause": top.root_cause,
        "fix": top.fix_suggestion,
    }


def _attach_reasoning_advisory(intent_model, reasoning, llm_result: Dict[str, Any]) -> None:
    algorithm_guess = getattr(reasoning, "llm_algorithm_guess", None)
    llm_summary = getattr(reasoning, "llm_summary", None)
    deeper_bugs = list(getattr(reasoning, "deeper_bug_hypotheses", []) or [])

    if not algorithm_guess and not llm_summary and not deeper_bugs:
        return

    intent_model.llm_advisory = {
        "provider": "gemini",
        "reasoning_mode": "mandatory_second_pass",
        "algorithm_type": algorithm_guess,
        "intent_confidence": llm_result.get("intent_confidence"),
        "bug_detected": llm_result.get("bug_detected"),
        "bug_type": llm_result.get("bug_type"),
        "bug_summary": llm_result.get("bug_summary"),
        "actual_behavior": llm_result.get("actual_behavior"),
        "root_cause": llm_result.get("root_cause"),
        "human_explanation": llm_summary,
        "suggested_fix": llm_result.get("suggested_fix"),
        "suspect_lines": list(llm_result.get("suspect_lines") or []),
        "buggy_expression": llm_result.get("buggy_expression"),
        "deeper_bugs": deeper_bugs,
    }
    if algorithm_guess:
        intent_model.source = "HYBRID"


def _build_metrics(intent_model, normalized_trace, reasoning, divergences, invariant_report, alignment_map, data_flow_graph, intent_steps) -> Metrics:
    alignment_scores = [entry.score for entry in alignment_map]
    execution_alignment_score = round(sum(alignment_scores) / len(alignment_scores), 2) if alignment_scores else 0.0
    divergence_severity_score = round(_divergence_severity_score(divergences), 2)
    invariant_violations = sum(1 for item in invariant_report if item.violation)
    invariant_coverage_score = round(
        ((len(invariant_report) - invariant_violations) / len(invariant_report)) if invariant_report else 1.0,
        2,
    )

    return Metrics(
        intent_confidence=intent_model.confidence,
        alignment_score=execution_alignment_score,
        divergence_score=divergence_severity_score,
        execution_steps=normalized_trace.total_steps,
        divergence_count=len(divergences),
        algorithm_detected=reasoning.llm_algorithm_guess or intent_model.inferred_algorithm,
        algorithm_variant=intent_model.algorithm_variant,
        execution_alignment_score=execution_alignment_score,
        divergence_severity_score=divergence_severity_score,
        invariant_coverage_score=invariant_coverage_score,
        invariant_violations=invariant_violations,
        aligned_steps=sum(1 for entry in alignment_map if entry.relation != "unknown"),
        data_flow_edges=len(data_flow_graph.get("edges", [])),
        intent_step_count=len(intent_steps),
    )


def _divergence_severity_score(divergences) -> float:
    severity_weight = {"CRITICAL": 1.0, "HIGH": 0.75, "MEDIUM": 0.45, "LOW": 0.2}
    if not divergences:
        return 0.0
    weighted = [severity_weight.get(item.severity, 0.2) for item in divergences]
    return min(1.0, sum(weighted) / max(len(weighted), 1))


def _divergence_report(divergences) -> List[Dict[str, Any]]:
    severity_weight = {"CRITICAL": 1.0, "HIGH": 0.75, "MEDIUM": 0.45, "LOW": 0.2}
    report: List[Dict[str, Any]] = []
    for divergence in divergences:
        payload = divergence.model_dump()
        payload["divergence_type"] = divergence.type
        payload["step_id"] = (
            divergence.causal_chain[0].step_index if divergence.causal_chain else None
        )
        payload["line_number"] = divergence.first_occurrence_line
        payload["causal_chain"] = [
            step.model_dump() if hasattr(step, "model_dump") else step
            for step in divergence.causal_chain
        ]
        payload["severity_score"] = severity_weight.get(divergence.severity, 0.2)
        report.append(payload)
    return report


def _attach_alignment_targets(graph: Dict[str, Any], alignment_map) -> None:
    if not graph.get("nodes"):
        return
    targets_by_step: Dict[int, List[str]] = {}
    for entry in alignment_map:
        relation = getattr(entry, "relation", None) or (entry.get("relation") if isinstance(entry, dict) else None)
        intent_step_id = getattr(entry, "intent_step_id", None) or (entry.get("intent_step_id") if isinstance(entry, dict) else None)
        execution_step_id = getattr(entry, "execution_step_id", None) or (entry.get("execution_step_id") if isinstance(entry, dict) else None)
        if execution_step_id is None or not intent_step_id:
            continue
        label = f"{intent_step_id} ({relation})" if relation else intent_step_id
        targets_by_step.setdefault(execution_step_id, []).append(label)

    for node in graph.get("nodes", []):
        detail = node.get("detail") or {}
        step_id = detail.get("step")
        if step_id is None:
            continue
        detail["alignment_targets"] = list(targets_by_step.get(step_id, []))
