from __future__ import annotations

import json
from typing import Any, Dict
from urllib import error, request

from backend.config import get_gemini_api_key, get_gemini_model, load_env_file


class GeminiConfigurationError(ValueError):
    pass


class GeminiReasoningError(RuntimeError):
    pass


def analyze_reasoning_with_llm(
    *,
    code: str,
    trace_summary: Dict[str, Any],
    divergence_summary: Dict[str, Any],
    structural_intent: Dict[str, Any],
    invariants_checked: list[Dict[str, Any]] | None = None,
    api_key: str | None = None,
    cognitive_addendum: str = "",
) -> Dict[str, Any]:
    load_env_file()
    resolved_api_key = get_gemini_api_key(api_key)
    if not resolved_api_key:
        raise GeminiConfigurationError(
            "Gemini reasoning is mandatory. Set GEMINI_API_KEY in .env or send gemini_api_key in the request."
        )

    prompt = _build_prompt(
        code,
        trace_summary,
        divergence_summary,
        structural_intent,
        invariants_checked or [],
        cognitive_addendum,
    )
    payload = {
        "system_instruction": {
            "parts": [
                {
                    "text": (
                        "You are an elite programming interview mentor and debugging expert who reasons like an "
                        "expert programmer that has completed every LeetCode problem, including the hardest heap, "
                        "graph, DP, tree, greedy, and shortest-path problems. "
                        "Behave like a precise senior programmer: identify the real algorithm family, explain intent "
                        "cleanly, and give fix suggestions grounded in the deterministic trace. "
                        "Never invent execution facts beyond the provided trace summary and divergence evidence. "
                        "Return JSON only."
                    )
                }
            ]
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}],
            }
        ],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "application/json",
        },
    }

    gemini_model = get_gemini_model()
    endpoint = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{gemini_model}:generateContent"
        f"?key={resolved_api_key}"
    )
    req = request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:  # pragma: no cover - network path
        with request.urlopen(req, timeout=45) as response:
            body = response.read().decode("utf-8")
    except error.HTTPError as exc:  # pragma: no cover - network path
        detail = exc.read().decode("utf-8", errors="ignore")
        raise GeminiReasoningError(f"Gemini request failed with HTTP {exc.code}: {detail}") from exc
    except error.URLError as exc:  # pragma: no cover - network path
        raise GeminiReasoningError(f"Gemini request failed: {exc.reason}") from exc

    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as exc:  # pragma: no cover - network path
        raise GeminiReasoningError("Gemini returned malformed JSON.") from exc

    text = _extract_gemini_text(parsed)
    data = _parse_json_payload(text)
    if not data:
        raise GeminiReasoningError("Gemini did not return the required JSON reasoning payload.")
    return data


def _build_prompt(
    code: str,
    trace_summary: Dict[str, Any],
    divergence_summary: Dict[str, Any],
    structural_intent: Dict[str, Any],
    invariants_checked: list[Dict[str, Any]],
    cognitive_addendum: str = "",
) -> str:
    return (
        "You are the mandatory second-pass reasoning engine.\n"
        "A deterministic first pass has already parsed the program, executed it, traced it, and produced rule-based divergences.\n"
        "Your job is not to re-run execution. Your job is to reason like an expert programmer who has completed every LeetCode problem.\n"
        "If the structural pass under-classified the algorithm, correct the algorithm family in your reasoning.\n"
        "Be especially sharp about heaps, priority queues, BFS, DFS, Dijkstra, MST, DP, recursion, greedy, and sliding-window patterns.\n"
        "Return JSON with exactly these keys:\n"
        "algorithm_type: short snake_case label, preferably matching canonical families such as heap_min_element, heap_top_k, heap_merge_k_lists, bfs_standard, dfs_recursive, dijkstra, graph_mst, dp_1d_linear, dp_2d_grid, sliding_window_fixed, sliding_window_variable, binary_search_array, binary_search_answer_space, backtracking, recursion_memo, union_find, monotonic_stack, monotonic_queue, interval_merge, matrix_traversal\n"
        "intent_confidence: float between 0 and 1 for how confident you are about the algorithm_type\n"
        "bug_detected: boolean\n"
        "bug_type: choose the most specific semantic bug class you can. Valid values are heap_index_error, wrong_index_access, wrong_state_selection, wrong_condition, incorrect_comparison, wrong_return_value, off_by_one, late_visited_mark, wrong_window_update, dp_state_inconsistency, invariant_violation, missing_state_update, premature_termination, wrong_algorithm_assumption, wrong_data_structure_usage, semantic_mismatch, none\n"
        "bug_summary: one sentence summary of the semantic mistake\n"
        "intended_behavior: 1-3 sentence human explanation of what the programmer meant the code to do\n"
        "actual_behavior: 1-3 sentence human explanation of what the code actually does at runtime\n"
        "root_cause: 1-2 sentence explanation of the concrete mistake\n"
        "human_explanation: 2-4 natural sentences written like a strong human code reviewer, not like a schema or JSON dump\n"
        "suggested_fix: 1-2 sentence concrete fix\n"
        "suspect_lines: array of 1-based line numbers most responsible for the bug, or [] if no bug\n"
        "buggy_expression: short code expression if identifiable, else null\n"
        "expected_state: small JSON object for the key expected semantic state when useful, else null\n"
        "actual_state: small JSON object for the key wrong semantic state when useful, else null\n"
        "deeper_bugs: array of short natural-language bug hypotheses grounded in the trace\n"
        "This schema is intentionally general and must work for any algorithm family, not only heaps.\n"
        "If the code is semantically correct, set bug_detected to false, bug_type to none, suspect_lines to [], and keep suggested_fix empty.\n\n"
        f"Code:\n{code}\n\n"
        f"Structural first-pass result:\n{json.dumps(structural_intent, ensure_ascii=True)}\n\n"
        f"Execution trace summary:\n{json.dumps(trace_summary, ensure_ascii=True)}\n\n"
        f"Invariants checked:\n{json.dumps(invariants_checked, ensure_ascii=True)}\n\n"
        f"Detected divergence summary:\n{json.dumps(divergence_summary, ensure_ascii=True)}\n"
        + (
            f"\nCognitive profile of this programmer:\n{cognitive_addendum}\n"
            if cognitive_addendum
            else ""
        )
    )


def _extract_gemini_text(payload: Dict[str, Any]) -> str:
    parts: list[str] = []
    for candidate in payload.get("candidates", []) or []:
        content = candidate.get("content", {}) or {}
        for part in content.get("parts", []) or []:
            text = part.get("text")
            if text:
                parts.append(text)
    return "\n".join(parts)


def _parse_json_payload(text: str) -> Dict[str, Any] | None:
    if not text:
        return None
    start = text.find("{")
    end = text.rfind("}")
    payload = text[start : end + 1] if start != -1 and end != -1 else text
    try:
        data = json.loads(payload)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    return {
        "algorithm_type": _clean_text(data.get("algorithm_type")),
        "intent_confidence": _coerce_float(data.get("intent_confidence")),
        "bug_detected": _coerce_bool(data.get("bug_detected")),
        "bug_type": _clean_text(data.get("bug_type")),
        "bug_summary": _clean_text(data.get("bug_summary")),
        "intended_behavior": _clean_text(data.get("intended_behavior")),
        "actual_behavior": _clean_text(data.get("actual_behavior")),
        "root_cause": _clean_text(data.get("root_cause")),
        "deeper_bugs": _coerce_string_list(data.get("deeper_bugs")),
        "human_explanation": _clean_text(data.get("human_explanation")),
        "suggested_fix": _clean_text(data.get("suggested_fix")),
        "suspect_lines": _coerce_int_list(data.get("suspect_lines")),
        "buggy_expression": _clean_text(data.get("buggy_expression")),
        "expected_state": _coerce_state(data.get("expected_state")),
        "actual_state": _coerce_state(data.get("actual_state")),
    }


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "1"}
    if isinstance(value, (int, float)):
        return bool(value)
    return False


def _coerce_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return None


def _coerce_int_list(value: Any) -> list[int]:
    if not isinstance(value, list):
        return []
    lines: list[int] = []
    for item in value:
        try:
            parsed = int(item)
        except (TypeError, ValueError):
            continue
        if parsed > 0:
            lines.append(parsed)
    return sorted(set(lines))


def _coerce_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    cleaned: list[str] = []
    for item in value:
        text = _clean_text(item)
        if text:
            cleaned.append(text)
    return cleaned


def _coerce_state(value: Any) -> Any:
    if isinstance(value, (dict, list, str, int, float, bool)) or value is None:
        return value
    return _clean_text(value)
