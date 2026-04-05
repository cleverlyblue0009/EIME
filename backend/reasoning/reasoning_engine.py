from __future__ import annotations

from typing import Any, Dict, List

from backend.api.models import ReasoningOutput
from backend.reasoning.llm_reasoner import analyze_reasoning_with_llm

SEVERITY_ORDER = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}

ALGO_TEMPLATES = {
    "sliding_window_fixed": "Fixed sliding window advances one contiguous window of constant width and must evaluate every valid start position exactly once.",
    "sliding_window_variable": "Variable sliding window grows and shrinks while preserving a validity condition on the current interval.",
    "binary_search_array": "Binary search keeps an ordered candidate interval and removes half of it on every iteration.",
    "binary_search_answer_space": "Answer-space binary search converges on a monotone boundary using a feasibility predicate.",
    "merge_sort": "Merge sort recursively solves both halves and then merges them into one ordered result.",
    "quick_sort_lomuto": "Quick sort partitions around a pivot and recursively sorts the partitions.",
    "heap_min_element": "After heapify or repeated heap pushes, the minimum element of a min-heap is always stored at index 0.",
    "heap_top_k": "Top-k heap logic keeps exactly the best k candidates seen so far.",
    "heap_merge_k_lists": "Heap merge repeatedly chooses the globally smallest available list head.",
    "bfs_standard": "Breadth-first search explores the graph level by level from the starting frontier.",
    "bfs_level_order": "Level-order BFS processes exactly one queue snapshot per depth level.",
    "dfs_recursive": "Recursive DFS follows one path deeply, then unwinds and explores alternatives.",
    "dfs_iterative": "Iterative DFS simulates the recursive call stack using an explicit LIFO structure.",
    "dp_1d_linear": "1D dynamic programming computes each state from smaller already-solved states in index order.",
    "dp_1d_kadane": "Kadane's algorithm tracks the best subarray ending at each position and the best overall answer.",
    "dp_2d_grid": "2D grid DP propagates solutions from already-solved neighboring cells.",
    "dp_lcs": "LCS DP compares prefixes of two strings and reuses optimal prefix answers.",
    "dp_knapsack_01": "0/1 knapsack DP iterates capacity carefully so each item contributes at most once.",
    "dp_edit_distance": "Edit-distance DP compares prefix pairs and chooses the cheapest local edit.",
    "tree_traversal": "Tree traversal visits nodes in a precise structural order.",
    "tree_dp": "Tree DP combines child results to compute parent state and often a global optimum.",
    "monotonic_stack": "Monotonic stack preserves order so next-greater or span relationships can be resolved quickly.",
    "monotonic_queue": "Monotonic queue keeps the best candidate at the front while the window slides.",
    "union_find": "Union-Find tracks connected components through root finding, compression, and balanced unions.",
    "trie_insert_search": "Trie operations walk linked prefix nodes one character at a time.",
    "dijkstra": "Dijkstra finalizes the smallest tentative distance and relaxes outgoing edges.",
    "topological_sort_kahn": "Kahn's algorithm repeatedly removes zero in-degree nodes from a DAG.",
    "backtracking": "Backtracking explores the choice tree by making one choice, recursing, and restoring state before the next branch.",
    "interval_merge": "Interval merging sorts ranges and coalesces overlaps in order.",
    "recursion_memo": "Memoized recursion solves overlapping subproblems top-down and reuses cached answers.",
    "graph_mst": "Minimum spanning tree logic repeatedly picks the cheapest edge that keeps the partial tree valid.",
    "matrix_traversal": "Matrix traversal depends on direction and boundary invariants to visit every intended cell exactly once.",
}


def collect_llm_reasoning(divergences, intent, normalized_trace, code: str = "", gemini_api_key: str | None = None) -> Dict[str, Any]:
    top = None
    if divergences:
        top = sorted(divergences, key=lambda item: SEVERITY_ORDER.get(item.severity, 0), reverse=True)[0]

    return analyze_reasoning_with_llm(
        code=code,
        trace_summary=_trace_summary(normalized_trace),
        divergence_summary=_divergence_summary(top),
        structural_intent={
            "algorithm": intent.inferred_algorithm,
            "variant": intent.algorithm_variant,
            "goal": intent.programmer_goal,
            "pitfalls": list(intent.known_pitfalls),
        },
        invariants_checked=[
            {
                "description": item.description,
                "formal_expression": item.formal_expression,
                "criticality": item.criticality,
            }
            for item in getattr(intent, "invariants", []) or []
        ],
        api_key=gemini_api_key,
    )


def generate(
    divergences,
    intent,
    normalized_trace,
    *,
    llm_result: Dict[str, Any] | None = None,
    code: str = "",
    gemini_api_key: str | None = None,
) -> ReasoningOutput:
    top = None
    if divergences:
        top = sorted(divergences, key=lambda item: SEVERITY_ORDER.get(item.severity, 0), reverse=True)[0]

    llm_result = llm_result or collect_llm_reasoning(
        divergences,
        intent,
        normalized_trace,
        code=code,
        gemini_api_key=gemini_api_key,
    )
    semantic_algorithm = (llm_result or {}).get("algorithm_type") or intent.inferred_algorithm
    llm_confidence = (llm_result or {}).get("intent_confidence")

    return ReasoningOutput(
        executive_summary=_executive_summary(top, intent, llm_result),
        intended_behavior=_build_intended_behavior(intent, llm_result),
        actual_behavior=_build_actual_behavior(top, llm_result),
        divergence_explanation=_build_divergence_explanation(top, intent, llm_result),
        root_cause=_build_root_cause(top, intent, llm_result),
        fix_suggestion=_build_fix_suggestion(top, llm_result),
        algorithm_explanation=ALGO_TEMPLATES.get(
            semantic_algorithm,
            (llm_result or {}).get("intended_behavior")
            or f"{semantic_algorithm} depends on preserving its core invariants at each step.",
        ),
        confidence=round(max(intent.confidence, llm_confidence or 0.0), 2),
        llm_summary=(llm_result or {}).get("human_explanation"),
        llm_algorithm_guess=(llm_result or {}).get("algorithm_type"),
        deeper_bug_hypotheses=list((llm_result or {}).get("deeper_bugs") or []),
    )


def _executive_summary(top, intent, llm_result: Dict[str, Any]) -> str:
    semantic_algorithm = (llm_result or {}).get("algorithm_type") or intent.inferred_algorithm
    bug_summary = (llm_result or {}).get("bug_summary")
    if top is None:
        if bug_summary:
            return bug_summary
        if semantic_algorithm != intent.inferred_algorithm:
            return (
                f"The deterministic trace completed cleanly, but Gemini reclassified this code as {semantic_algorithm.replace('_', ' ')} "
                f"instead of {intent.inferred_algorithm.replace('_', ' ')}."
            )
        return "Execution aligns with the inferred algorithmic intent and no semantic divergence was detected."
    if top.type == "WINDOW_INCOMPLETENESS":
        missing = top.missing_state.get("missing_iterations") if isinstance(top.missing_state, dict) else None
        if missing:
            return (
                f"This {intent.inferred_algorithm} implementation skips {missing} required iteration(s). "
                "The loop stops before the final semantic state is produced."
            )
    if bug_summary:
        return bug_summary
    if top.type in {"LOOP_BOUND_ERROR", "LOOP_MISSING_LAST_ITERATION", "OFF_BY_ONE", "OFF_BY_ONE_BOUND"}:
        return (
            f"This {intent.inferred_algorithm} implementation diverges at its boundary condition. "
            "A required final state is excluded from execution."
        )
    return f"Execution diverges from the inferred {semantic_algorithm.replace('_', ' ')} intent at {top.divergence_point or f'line {top.first_occurrence_line}'}."


def _build_intended_behavior(intent, llm_result: Dict[str, Any]) -> str:
    llm_text = (llm_result or {}).get("intended_behavior")
    llm_algorithm = (llm_result or {}).get("algorithm_type")
    if llm_text:
        if llm_algorithm and llm_algorithm != intent.inferred_algorithm:
            return (
                f"{llm_text} Gemini reclassified the function as {llm_algorithm.replace('_', ' ')}, "
                f"while the structural pass had labeled it as {intent.inferred_algorithm.replace('_', ' ')}."
            )
        return llm_text

    invariant_text = ""
    if getattr(intent, "invariants", None):
        primary = intent.invariants[0]
        invariant_text = f" The key invariant is: {primary.description}"
    return (
        f"{intent.programmer_goal} "
        f"The structural pass inferred {intent.inferred_algorithm.replace('_', ' ')}"
        f"{f' ({intent.algorithm_variant})' if intent.algorithm_variant else ''}."
        f"{invariant_text}"
    )


def _build_actual_behavior(top, llm_result: Dict[str, Any]) -> str:
    llm_text = (llm_result or {}).get("actual_behavior")
    if llm_text:
        return llm_text
    if top is None:
        return "The observed execution produced all expected semantic states."
    parts = [top.actual_behavior]
    if top.actual_state is not None:
        parts.append(f"Observed state: {_human_state(top.actual_state)}.")
    if top.missing_state is not None:
        parts.append(f"Missing state: {_human_state(top.missing_state)}.")
    if top.extra_state is not None:
        parts.append(f"Extra state: {_human_state(top.extra_state)}.")
    return " ".join(parts)


def _build_divergence_explanation(top, intent, llm_result: Dict[str, Any]) -> str:
    llm_explanation = (llm_result or {}).get("human_explanation")
    if llm_explanation and top is not None:
        parts = [llm_explanation]
        if top.expected_state is not None:
            parts.append(f"Expected state: {_human_state(top.expected_state)}.")
        if top.actual_state is not None:
            parts.append(f"Actual state: {_human_state(top.actual_state)}.")
        return " ".join(parts)
    if llm_explanation:
        return llm_explanation
    if top is None:
        return "No divergence explanation is needed because the observed behavior aligns with the inferred intent."

    invariant_text = intent.invariants[0].description if getattr(intent, "invariants", None) else "the key algorithm invariant"
    parts = [
        f"The first semantic divergence occurs at {top.divergence_point or f'line {top.first_occurrence_line}'}, where {invariant_text.lower()} stops holding.",
        f"Expected behavior: {top.expected_behavior}",
        f"Actual behavior: {top.actual_behavior}",
    ]
    if top.expected_state is not None:
        parts.append(f"Expected state: {_human_state(top.expected_state)}.")
    if top.actual_state is not None:
        parts.append(f"Actual state: {_human_state(top.actual_state)}.")
    if top.missing_state is not None:
        parts.append(f"Missing state: {_human_state(top.missing_state)}.")
    if top.causal_chain:
        chain_text = " ".join(
            f"Step {step.step_index} at line {step.lineno}: {step.description}. {step.why_this_matters}"
            for step in top.causal_chain
        )
        parts.append(chain_text)
    parts.append(top.algorithm_context)
    return " ".join(part for part in parts if part)


def _build_root_cause(top, intent, llm_result: Dict[str, Any]) -> str:
    llm_root_cause = (llm_result or {}).get("root_cause")
    if llm_root_cause:
        return llm_root_cause
    if top is None:
        return "No root-cause issue was identified."
    if top.root_cause:
        return top.root_cause
    return (
        f"The root cause is {top.type.replace('_', ' ').lower()} in the {intent.inferred_algorithm.replace('_', ' ')} implementation, "
        f"starting at {top.divergence_point or f'line {top.first_occurrence_line}'}."
    )


def _build_fix_suggestion(top, llm_result: Dict[str, Any]) -> str:
    llm_fix = (llm_result or {}).get("suggested_fix")
    if llm_fix:
        return llm_fix
    if top is None:
        return "No code change is needed."
    return top.fix_suggestion or "Apply the smallest code change that restores the missing expected state."


def _trace_summary(normalized_trace) -> Dict[str, Any]:
    steps = getattr(normalized_trace, "steps", []) or []
    loops = getattr(normalized_trace, "loop_summaries", []) or []
    functions = getattr(normalized_trace, "function_calls", []) or []

    interesting_steps = []
    if steps:
        sample = steps[:4] + steps[-4:]
        seen: set[int] = set()
        for step in sample:
            if step.step_id in seen:
                continue
            seen.add(step.step_id)
            interesting_steps.append(
                {
                    "step_id": step.step_id,
                    "line": step.lineno,
                    "description": step.description,
                    "operation": step.operation_type or step.operation,
                    "variables": step.focus_variables or step.variable_snapshot,
                }
            )

    return {
        "total_steps": len(steps),
        "functions": [
            {"name": call.function_name, "call_site": call.call_site_line}
            for call in functions[:8]
            if call.function_name != "<module>"
        ],
        "loops": [
            {
                "header_line": loop.header_line,
                "iterations": loop.iteration_count,
                "mutated": loop.variables_mutated[:6],
            }
            for loop in loops[:6]
        ],
        "final_state": getattr(normalized_trace, "final_state", {}),
        "interesting_steps": interesting_steps,
    }


def _divergence_summary(top) -> Dict[str, Any]:
    if top is None:
        return {"type": None, "state": None}
    return {
        "type": top.type,
        "line": top.first_occurrence_line,
        "expected_behavior": top.expected_behavior,
        "actual_behavior": top.actual_behavior,
        "expected_state": top.expected_state,
        "actual_state": top.actual_state,
        "missing_state": top.missing_state,
    }


def _human_state(value: Any) -> str:
    if isinstance(value, dict):
        return ", ".join(f"{key}={value[key]!r}" for key in value)
    if isinstance(value, list):
        preview = ", ".join(repr(item) for item in value[:6])
        suffix = ", ..." if len(value) > 6 else ""
        return f"[{preview}{suffix}]"
    return repr(value)
