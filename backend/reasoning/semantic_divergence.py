from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List

from backend.api.models import CausalStep, Divergence

_GENERIC_FIXES = {
    "",
    "none",
    "n/a",
    "no fix needed",
    "no code change is needed.",
    "no code change is needed",
}

_BUG_TYPE_MAP = {
    "heap_index_error": "HEAP_INDEX_ERROR",
    "wrong_index_access": "WRONG_INDEX_ACCESS",
    "wrong_state_selection": "WRONG_STATE_SELECTION",
    "wrong_condition": "WRONG_CONDITION_CHECK",
    "incorrect_comparison": "WRONG_CONDITION_CHECK",
    "wrong_return_value": "WRONG_RETURN_VALUE",
    "off_by_one": "OFF_BY_ONE",
    "late_visited_mark": "BFS_VISITED_LATE",
    "wrong_window_update": "WRONG_WINDOW_UPDATE",
    "dp_state_inconsistency": "DP_STATE_INCONSISTENCY",
    "invariant_violation": "INVARIANT_VIOLATION",
    "missing_state_update": "MISSING_STATE_UPDATE",
    "premature_termination": "PREMATURE_TERMINATION",
    "wrong_algorithm_assumption": "INVARIANT_VIOLATION",
    "wrong_data_structure_usage": "SEMANTIC_MISMATCH",
    "semantic_mismatch": "SEMANTIC_MISMATCH",
    "none": None,
}


def build_semantic_divergences(
    llm_result: Dict[str, Any],
    trace: Any,
    intent: Any,
    parse_context: Dict[str, Any],
    existing_divergences: Iterable[Divergence] | None = None,
) -> List[Divergence]:
    if not _should_emit_divergence(llm_result):
        return []

    existing = list(existing_divergences or [])
    suspect_lines = _resolve_suspect_lines(llm_result, parse_context)
    step = _find_best_step(trace, suspect_lines, llm_result.get("buggy_expression"))
    first_line = step.lineno if step is not None else (suspect_lines[0] if suspect_lines else _fallback_line(trace))

    divergence_type = _resolve_divergence_type(llm_result, intent, step)
    if any(
        item.type == divergence_type and item.first_occurrence_line == first_line
        for item in existing
    ):
        return []

    expected_state, actual_state = _resolve_states(llm_result, step, divergence_type)
    affected_variables = _affected_variables(step, llm_result.get("buggy_expression"))
    actual_behavior = (
        llm_result.get("actual_behavior")
        or llm_result.get("bug_summary")
        or llm_result.get("human_explanation")
        or "The observed result does not match the intended algorithm."
    )
    expected_behavior = (
        llm_result.get("intended_behavior")
        or getattr(intent, "programmer_goal", "")
        or "Preserve the intended algorithm invariant."
    )
    algorithm_type = llm_result.get("algorithm_type") or getattr(intent, "inferred_algorithm", "algorithm")
    explanation = _compose_explanation(llm_result, step, expected_behavior, actual_behavior)
    fix_suggestion = _normalize_fix(llm_result.get("suggested_fix"))

    causal_chain = []
    if step is not None:
        causal_chain.append(
            CausalStep(
                step_index=step.step_id,
                description=step.description,
                lineno=step.lineno,
                variable_state=step.variable_snapshot,
                why_this_matters=(
                    llm_result.get("root_cause")
                    or llm_result.get("bug_summary")
                    or f"This step is where the {algorithm_type} implementation drifts semantically."
                ),
            )
        )

    return [
        Divergence(
            type=divergence_type,
            severity=_resolve_severity(divergence_type),
            causal_chain=causal_chain,
            first_occurrence_line=first_line,
            symptom_line=first_line,
            expected_behavior=expected_behavior,
            actual_behavior=actual_behavior,
            affected_variables=affected_variables,
            affected_lines=sorted(set([first_line] + suspect_lines)),
            algorithm_context=(
                f"Gemini second pass recognized this as {algorithm_type} and flagged a semantic mistake "
                "that the deterministic rule pass did not classify on its own."
            ),
            fix_suggestion=fix_suggestion,
            expected_state=expected_state,
            actual_state=actual_state,
            divergence_point=f"step {step.step_id} at line {step.lineno}" if step is not None else f"line {first_line}",
            explanation=explanation,
            root_cause=(
                llm_result.get("root_cause")
                or llm_result.get("bug_summary")
                or "The code reaches the end of execution, but the chosen operation does not satisfy the intended algorithm."
            ),
            evidence={
                "source": "LLM_SECOND_PASS",
                "advisory": True,
                "algorithm_type": algorithm_type,
                "bug_type": llm_result.get("bug_type"),
                "buggy_expression": llm_result.get("buggy_expression"),
                "suspect_lines": suspect_lines,
            },
        )
    ]


def _should_emit_divergence(llm_result: Dict[str, Any]) -> bool:
    if not llm_result:
        return False
    if llm_result.get("bug_detected") is True:
        return True
    if llm_result.get("bug_type") and llm_result.get("bug_type") != "none":
        return True
    fix = (llm_result.get("suggested_fix") or "").strip().lower()
    if fix and fix not in _GENERIC_FIXES:
        return True
    explanation = " ".join(
        value for value in [
            llm_result.get("bug_summary"),
            llm_result.get("actual_behavior"),
            llm_result.get("human_explanation"),
            llm_result.get("root_cause"),
        ]
        if isinstance(value, str)
    ).lower()
    return any(token in explanation for token in [" wrong ", " should ", " instead ", " bug", " not the ", "incorrect"])


def _resolve_divergence_type(llm_result: Dict[str, Any], intent: Any, step: Any) -> str:
    bug_type = (llm_result.get("bug_type") or "").strip().lower()
    mapped = _BUG_TYPE_MAP.get(bug_type)
    if mapped:
        return mapped

    inferred_from_text = _infer_divergence_from_text(llm_result, step)
    if inferred_from_text:
        return inferred_from_text

    algorithm_type = (llm_result.get("algorithm_type") or getattr(intent, "inferred_algorithm", "") or "").lower()
    if algorithm_type.startswith("heap"):
        snippet = (llm_result.get("buggy_expression") or getattr(step, "code_snippet", "") or "").lower()
        if "[" in snippet and "]" in snippet:
            return "HEAP_INDEX_ERROR"
        return "WRONG_RETURN_VALUE"
    if algorithm_type.startswith("dp"):
        return "DP_STATE_INCONSISTENCY"
    if "bfs" in algorithm_type and "visited" in _semantic_text(llm_result):
        return "BFS_VISITED_LATE"
    return "INVARIANT_VIOLATION"


def _resolve_severity(divergence_type: str) -> str:
    if divergence_type in {
        "WRONG_RETURN_VALUE",
        "HEAP_INDEX_ERROR",
        "WRONG_INDEX_ACCESS",
        "WRONG_STATE_SELECTION",
        "DP_STATE_INCONSISTENCY",
        "WRONG_CONDITION_CHECK",
    }:
        return "HIGH"
    if divergence_type in {"OFF_BY_ONE", "WRONG_WINDOW_UPDATE", "BFS_VISITED_LATE"}:
        return "MEDIUM"
    return "MEDIUM"


def _resolve_suspect_lines(llm_result: Dict[str, Any], parse_context: Dict[str, Any]) -> List[int]:
    lines = list(llm_result.get("suspect_lines") or [])
    if lines:
        return sorted(set(line for line in lines if isinstance(line, int) and line > 0))

    buggy_expression = llm_result.get("buggy_expression")
    if not buggy_expression:
        return []
    line_index = parse_context.get("line_index", {}) if parse_context else {}
    matches = [
        lineno
        for lineno, payload in line_index.items()
        if buggy_expression in (payload.get("code_line") or "")
    ]
    return sorted(set(matches))


def _find_best_step(trace: Any, suspect_lines: List[int], buggy_expression: str | None):
    steps = list(getattr(trace, "steps", []) or [])
    if suspect_lines:
        for line in suspect_lines:
            for step in steps:
                if step.lineno == line:
                    return step
    if buggy_expression:
        for step in reversed(steps):
            snippet = step.code_snippet or step.code_line or ""
            if buggy_expression in snippet:
                return step
    for step in reversed(steps):
        if (step.operation_type or step.operation) == "return":
            return step
    return steps[-1] if steps else None


def _fallback_line(trace: Any) -> int:
    steps = list(getattr(trace, "steps", []) or [])
    return steps[-1].lineno if steps else 1


def _resolve_states(llm_result: Dict[str, Any], step: Any, divergence_type: str) -> tuple[Any, Any]:
    expected_state = llm_result.get("expected_state")
    actual_state = llm_result.get("actual_state")

    if divergence_type in {"HEAP_INDEX_ERROR", "WRONG_INDEX_ACCESS", "WRONG_STATE_SELECTION"} and step is not None:
        inferred_expected, inferred_actual = _infer_index_access_states(step, llm_result, divergence_type)
        expected_state = expected_state if expected_state is not None else inferred_expected
        actual_state = actual_state if actual_state is not None else inferred_actual

    if actual_state is None and step is not None:
        actual_state = _focused_snapshot(step, llm_result.get("buggy_expression"))
    return expected_state, actual_state


def _infer_index_access_states(step: Any, llm_result: Dict[str, Any], divergence_type: str) -> tuple[Any, Any]:
    snippet = llm_result.get("buggy_expression") or step.code_snippet or step.code_line or ""
    match = re.search(r"([A-Za-z_][A-Za-z0-9_]*)\[(\d+)\]", snippet)
    if not match:
        return None, None
    name = match.group(1)
    index = int(match.group(2))
    heap_value = step.variable_snapshot.get(name)
    if not isinstance(heap_value, list) or not heap_value:
        return None, None

    expected = None
    if divergence_type == "HEAP_INDEX_ERROR":
        expected = {
            "minimum_expression": f"{name}[0]",
            "minimum_value": heap_value[0],
        }
    else:
        expected = {
            "expected_collection": name,
            "expected_note": "The intended semantic choice should come from a different element or condition than the accessed slot.",
        }
    actual = {
        "accessed_expression": f"{name}[{index}]",
        "accessed_value": heap_value[index] if index < len(heap_value) else None,
        "collection_snapshot": heap_value,
    }
    return expected, actual


def _affected_variables(step: Any, buggy_expression: str | None) -> List[str]:
    variables: List[str] = []
    if step is not None:
        for name in list(step.write_accesses or []) + list(step.read_accesses or []) + list((step.variable_snapshot or {}).keys()):
            base = name.split("[", 1)[0].split(".", 1)[0]
            if base and base not in variables:
                variables.append(base)
            if len(variables) >= 5:
                return variables
    if buggy_expression:
        for token in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", buggy_expression):
            if token not in variables:
                variables.append(token)
    return variables[:5]


def _compose_explanation(
    llm_result: Dict[str, Any],
    step: Any,
    expected_behavior: str,
    actual_behavior: str,
) -> str:
    sentences = [
        llm_result.get("human_explanation"),
        llm_result.get("root_cause"),
    ]
    if step is not None and step.code_snippet:
        sentences.append(f"The critical step is line {step.lineno}, where `{step.code_snippet}` executes.")
    sentences.append(f"Intended behavior: {expected_behavior}")
    sentences.append(f"Observed behavior: {actual_behavior}")
    return " ".join(sentence for sentence in sentences if sentence)


def _normalize_fix(fix: Any) -> str:
    text = str(fix or "").strip()
    if not text or text.lower() in _GENERIC_FIXES:
        return "Adjust the buggy expression so it preserves the intended algorithm invariant."
    return text


def _semantic_text(llm_result: Dict[str, Any]) -> str:
    return " ".join(
        str(value)
        for value in [
            llm_result.get("bug_summary"),
            llm_result.get("actual_behavior"),
            llm_result.get("root_cause"),
            llm_result.get("human_explanation"),
            llm_result.get("buggy_expression"),
        ]
        if value
    ).lower()


def _infer_divergence_from_text(llm_result: Dict[str, Any], step: Any) -> str | None:
    text = _semantic_text(llm_result)
    snippet = (llm_result.get("buggy_expression") or getattr(step, "code_snippet", "") or "").lower()

    if any(token in text for token in ["wrong return", "returns the wrong", "returned the wrong", "incorrect return"]):
        return "WRONG_RETURN_VALUE"
    if ("[" in snippet and "]" in snippet) or "wrong index" in text or "index 0" in text or "index 1" in text:
        return "WRONG_INDEX_ACCESS"
    if any(token in text for token in ["wrong condition", "incorrect comparison", "comparison is wrong", "predicate is wrong"]):
        return "WRONG_CONDITION_CHECK"
    if any(token in text for token in ["visited too late", "mark visited after", "late visited"]):
        return "BFS_VISITED_LATE"
    if any(token in text for token in ["missing update", "never updates", "state is not updated"]):
        return "MISSING_STATE_UPDATE"
    if any(token in text for token in ["wrong state", "wrong choice", "wrong slot", "wrong element", "selected the wrong"]):
        return "WRONG_STATE_SELECTION"
    if any(token in text for token in ["off by one", "one too many", "one too few"]):
        return "OFF_BY_ONE"
    if any(token in text for token in ["premature", "stops too early", "returns early"]):
        return "PREMATURE_TERMINATION"
    if any(token in text for token in ["invariant", "semantic mismatch", "algorithm assumption", "wrong data structure"]):
        return "SEMANTIC_MISMATCH"
    return None


def _focused_snapshot(step: Any, buggy_expression: str | None) -> Any:
    snapshot = getattr(step, "variable_snapshot", {}) or {}
    if not isinstance(snapshot, dict):
        return snapshot

    if buggy_expression:
        tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", buggy_expression)
        focused = {token: snapshot[token] for token in tokens if token in snapshot}
        if focused:
            return focused

    reads = list(getattr(step, "read_accesses", []) or []) + list(getattr(step, "write_accesses", []) or [])
    focused: Dict[str, Any] = {}
    for name in reads:
        base = name.split("[", 1)[0].split(".", 1)[0]
        if base in snapshot and base not in focused:
            focused[base] = snapshot[base]
        if len(focused) >= 4:
            break
    return focused or snapshot
