from __future__ import annotations

from typing import Any


def _build_execution_line_counts(execution_trace: list[dict[str, Any]]) -> dict[int, int]:
    """Count how many times each source line was executed."""
    counts: dict[int, int] = {}
    for entry in execution_trace:
        if entry.get("event") != "line":
            continue
        line = entry.get("line")
        if line is None:
            continue
        counts[line] = counts.get(line, 0) + 1
    return counts


def _serialize_locals(locals_dict: dict[str, Any]) -> dict[str, Any]:
    """Shallow copy locals for safe inspection."""
    return dict(locals_dict)


def compute_divergence(
    execution_trace: list[dict[str, Any]], intent_result: dict[str, Any]
) -> dict[str, Any]:
    """Align execution to intent and surface divergence details."""
    intent_trace = intent_result.get("intent_trace", [])
    line_counts = _build_execution_line_counts(execution_trace)
    used_execution_indices: set[int] = set()
    aligned_pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    mismatches: list[dict[str, Any]] = []

    for intent_step in intent_trace:
        target_line = intent_step.get("line")
        match_idx = None
        for idx, exec_step in enumerate(execution_trace):
            if idx in used_execution_indices:
                continue
            if exec_step.get("line") == target_line:
                match_idx = idx
                break
        if match_idx is not None:
            used_execution_indices.add(match_idx)
            aligned_pairs.append((intent_step, execution_trace[match_idx]))
        else:
            mismatches.append(
                {
                    "step": intent_step.get("step", 0),
                    "line": target_line,
                    "type": "missing_step",
                    "expected": intent_step,
                    "actual": None,
                    "description": "Intent step did not occur in execution trace.",
                }
            )

    for intent_step, exec_step in aligned_pairs:
        intent_step_index = intent_step.get("step", 0)
        line = intent_step.get("line")
        actual_locals = _serialize_locals(exec_step.get("locals", {}))
        expected_locals = intent_step.get("expected_locals", {})

        for key, expected in expected_locals.items():
            if key not in actual_locals:
                continue
            actual_value = actual_locals[key]
            if str(expected) != str(actual_value):
                mismatches.append(
                    {
                        "step": exec_step.get("step", 0),
                        "line": line,
                        "type": "variable_mismatch",
                        "expected": expected,
                        "actual": actual_value,
                        "description": f"'{key}' differs: expected {expected}, got {actual_value}.",
                    }
                )

        if intent_step_index > 1 and line is not None:
            actual_count = line_counts.get(line, 0)
            if actual_count != intent_step_index:
                mismatches.append(
                    {
                        "step": exec_step.get("step", 0),
                        "line": line,
                        "type": "loop_count",
                        "expected": intent_step_index,
                        "actual": actual_count,
                        "description": f"Line {line} executed {actual_count} times vs expected {intent_step_index}.",
                    }
                )

        if any("len" in key.lower() for key in expected_locals):
            for candidate in ("result", "output", "data"):
                actual_value = exec_step.get("locals", {}).get(candidate)
                if isinstance(actual_value, list):
                    expected_length = next(
                        (
                            value
                            for key, value in expected_locals.items()
                            if "len" in key.lower() and isinstance(value, int)
                        ),
                        None,
                    )
                    if expected_length is not None and len(actual_value) != expected_length:
                        mismatches.append(
                            {
                                "step": exec_step.get("step", 0),
                                "line": line,
                                "type": "output_length",
                                "expected": expected_length,
                                "actual": len(actual_value),
                                "description": "Output length differs from intent expectation.",
                            }
                        )
                        break

    exception_entries = [
        entry for entry in execution_trace if entry.get("event") == "exception"
    ]
    for entry in exception_entries:
        mismatches.append(
            {
                "step": entry.get("step", 0),
                "line": entry.get("line"),
                "type": "exception",
                "expected": None,
                "actual": entry.get("value"),
                "description": "Execution raised an exception.",
            }
        )

    total_steps = len(execution_trace)
    score = min(len(mismatches) / max(total_steps, 1), 1.0)
    if score < 0.3:
        severity = "LOW"
    elif score < 0.7:
        severity = "MEDIUM"
    else:
        severity = "HIGH"

    first_divergence = None
    if mismatches:
        earliest = min(mismatches, key=lambda entry: entry.get("step", 0))
        first_divergence = earliest.get("description", "Unknown divergence")

    seen_descriptions: set[str] = set()
    causal_chain: list[str] = []
    for mismatch in mismatches:
        desc = mismatch.get("description", "")
        if desc and desc not in seen_descriptions and len(causal_chain) < 5:
            seen_descriptions.add(desc)
            causal_chain.append(desc)

    return {
        "mismatches": mismatches,
        "first_divergence": first_divergence,
        "score": score,
        "severity": severity,
        "causal_chain": causal_chain,
        "total_steps": total_steps,
        "aligned_steps": len(aligned_pairs),
    }
