from __future__ import annotations

import json
import logging
import os

from anthropic import Anthropic, HUMAN_PROMPT, AI_PROMPT
from typing import Any


def _pattern_confidence(label: str) -> float:
    """Map intent labels to heuristic confidence scores."""
    mapping = {
        "fibonacci_sequence": 0.9,
        "sequence_accumulation": 0.8,
        "sorting_algorithm": 0.75,
        "recursive_computation": 0.85,
        "matrix_traversal": 0.7,
        "string_processing": 0.65,
        "counting_or_aggregation": 0.6,
        "general_computation": 0.5,
    }
    return mapping.get(label, 0.5)


def _build_intent_trace(label: str, code: str, ir: dict[str, Any]) -> list[dict[str, Any]]:
    """Create an expected trace snapshot based on the detected pattern."""
    loops = ir.get("loops", [])
    base_line = loops[0]["lineno"] if loops else 0
    steps: list[dict[str, Any]] = []

    if label == "fibonacci_sequence":
        a, b = 0, 1
        for idx in range(4):
            steps.append(
                {
                    "step": idx + 1,
                    "line": base_line,
                    "expected_state": f"Iteration {idx+1} should produce (a,b)=({a},{b})",
                    "invariant": "b == previous a + previous b",
                    "expected_locals": {"a": a, "b": b},
                }
            )
            a, b = b, a + b
        return steps

    if label == "sequence_accumulation":
        for idx in range(3):
            expected_len = idx + 1
            steps.append(
                {
                    "step": expected_len,
                    "line": base_line,
                    "expected_state": f"Append adds item {expected_len}",
                    "invariant": "len(result) == number of loop iterations",
                    "expected_locals": {"len_result": expected_len},
                }
            )
        return steps

    if label == "sorting_algorithm":
        steps.append(
            {
                "step": 1,
                "line": base_line,
                "expected_state": "All input values should persist into the output",
                "invariant": "sorted(output) == sorted(input)",
                "expected_locals": {"output_ordered": True},
            }
        )
        steps.append(
            {
                "step": 2,
                "line": base_line,
                "expected_state": "Each swap brings elements closer to completion",
                "invariant": "no element lost",
                "expected_locals": {"swap_progress": "monotonic"},
            }
        )
        return steps

    if label == "recursive_computation":
        steps.append(
            {
                "step": 1,
                "line": base_line,
                "expected_state": "Function should invoke itself with smaller inputs",
                "invariant": "depth eventually reaches base case",
                "expected_locals": {"depth": "decreasing"},
            }
        )
        return steps

    if label == "matrix_traversal":
        steps.append(
            {
                "step": 1,
                "line": base_line,
                "expected_state": "Nested loops cover both dimensions",
                "invariant": "each cell visited exactly once",
                "expected_locals": {"i": "row index", "j": "column index"},
            }
        )
        return steps

    if label == "string_processing":
        steps.append(
            {
                "step": 1,
                "line": base_line,
                "expected_state": "Loop constructs strings by concatenating or joining components",
                "invariant": "result is string",
                "expected_locals": {"result": "string"},
            }
        )
        return steps

    if label == "counting_or_aggregation":
        steps.append(
            {
                "step": 1,
                "line": base_line,
                "expected_state": "Counter increments each loop",
                "invariant": "counter == number of processed items",
                "expected_locals": {"counter": "integer"},
            }
        )
        return steps

    for idx in range(2):
        steps.append(
            {
                "step": idx + 1,
                "line": base_line,
                "expected_state": "Variable assignments change state sequentially",
                "invariant": "assignments update locals",
                "expected_locals": {},
            }
        )
    return steps


def _detect_pattern(code: str, ir: dict[str, Any]) -> tuple[str, str]:
    """Determine the intent label and description from code heuristics."""
    lowered = code.lower()
    normalized = "".join(lowered.split())
    loops = ir.get("loops", [])
    has_loop = bool(loops)
    has_append = ".append(" in lowered
    has_sorted = ".sort()" in lowered or "sorted(" in lowered
    has_nested_loops = len(loops) >= 2
    has_recursion = ir.get("has_recursion", False)
    has_matrix_index = "[i][j]" in normalized or "[j][i]" in normalized
    has_string_concat = "+=" in lowered or "join(" in lowered
    has_counting = "+=1" in normalized or "+=1" in lowered
    fib_pattern = "a,b=b,a+b" in normalized
    fib_name = any(
        "fib" in entry.get("name", "").lower()
        for entry in ir.get("functions", [])
    ) or any(
        "fib" in entry.get("name", "").lower()
        for entry in ir.get("variables", [])
    )

    if fib_name or fib_pattern:
        return (
            "fibonacci_sequence",
            "The code iterates over Fibonacci-style pair updates.",
        )
    if has_loop and has_append and len(loops) == 1:
        return (
            "sequence_accumulation",
            "A loop builds up a list through repeated append operations.",
        )
    if has_nested_loops and (has_sorted or "swap" in lowered):
        return (
            "sorting_algorithm",
            "Nested loops are rearranging elements, suggesting a sorting pass.",
        )
    if has_recursion:
        return (
            "recursive_computation",
            "A function is calling itself, which suggests recursion.",
        )
    if has_nested_loops and has_matrix_index:
        return (
            "matrix_traversal",
            "Nested loops with two-dimensional indexing indicate matrix work.",
        )
    if has_loop and has_string_concat:
        return (
            "string_processing",
            "Loop-based concatenation or join hints at string assembly.",
        )
    if has_loop and has_counting:
        return (
            "counting_or_aggregation",
            "A loop increments counters, implying aggregation.",
        )
    return (
        "general_computation",
        "Default fallback when no more specific intent is detected.",
    )


logger = logging.getLogger(__name__)


def model_intent(code: str, ir: dict[str, Any]) -> dict[str, Any]:
    """Produce a rule-based intent label, description, and expectations."""
    intent_label, description = _detect_pattern(code, ir)
    confidence = _pattern_confidence(intent_label)
    intent_trace = _build_intent_trace(intent_label, code, ir)
    source = "rules"

    if intent_label == "general_computation":
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if api_key:
            ir_summary = (
                f"{len(ir.get('functions', []))} functions, "
                f"{len(ir.get('loops', []))} loops, "
                f"{len(ir.get('variables', []))} variables observed"
            )
            prompt = (
                f"{HUMAN_PROMPT}"
                "Given this Python code and its AST summary, describe in one sentence what it is intended to compute.\n"
                f"Code: {code}\n"
                f"AST summary: {ir_summary}\n"
                'Respond with JSON only: {"intent_label": str, "description": str}\n'
                f"{AI_PROMPT}"
            )
            try:
                client = Anthropic(api_key=api_key)
                response = client.completions.create(
                    model="claude-3.0",
                    prompt=prompt,
                    max_tokens_to_sample=200,
                    temperature=0.2,
                )
                completion = response.completion.strip()
                start = completion.find("{")
                end = completion.rfind("}")
                payload = completion
                if start != -1 and end != -1:
                    payload = completion[start : end + 1]
                parsed = json.loads(payload)
                llm_label = parsed.get("intent_label")
                llm_description = parsed.get("description")
                if llm_label:
                    intent_label = llm_label
                if llm_description:
                    description = llm_description
                confidence = min(1.0, max(confidence, 0.7))
                source = "rules+llm"
            except Exception as exc:  # pragma: no cover - fallback
                logger.warning("Anthropic intent refinement failed: %s", exc)

    return {
        "intent_label": intent_label,
        "description": description,
        "confidence": confidence,
        "source": source,
        "intent_trace": intent_trace,
    }
