from __future__ import annotations

import json
import logging
import os

from anthropic import Anthropic, HUMAN_PROMPT, AI_PROMPT
from typing import Any

logger = logging.getLogger(__name__)


def _summarize_actual_behavior(divergence: dict[str, Any]) -> str:
    """Create a short description of what happened during execution."""
    if not divergence.get("mismatches"):
        return "Execution completed without detected divergence."
    return "Divergence chain: " + " | ".join(divergence.get("causal_chain", []))


def _suggest_fix(divergence: dict[str, Any]) -> str:
    """Build a heuristic suggested fix from divergence details."""
    for mismatch in divergence.get("mismatches", []):
        mismatch_type = mismatch.get("type")
        line = mismatch.get("line")
        if mismatch_type == "loop_count":
            expected = mismatch.get("expected")
            actual = mismatch.get("actual")
            if isinstance(expected, int) and isinstance(actual, int):
                if actual < expected:
                    return f"Increase the iteration range (e.g., range(n+1)) or adjust bound at line {line}."
                if actual > expected:
                    return f"Reduce loop iterations to match intent at line {line}."
        if mismatch_type == "variable_mismatch":
            desc = mismatch.get("description", "").lower()
            if "result" in desc or "accumulator" in desc:
                return f"Initialize or reset the accumulator before the loop at line {line}."
        if mismatch_type == "exception":
            actual = mismatch.get("actual")
            return f"Handle exception {actual} around line {line}."
    if divergence.get("first_divergence"):
        return f"Review the logic around the first divergent step: {divergence['first_divergence']}"
    return "Review the logic around the first divergent step."


def generate_reasoning(
    code: str, intent_result: dict[str, Any], divergence: dict[str, Any]
) -> dict[str, Any]:
    """Produce template-based reasoning about intent, execution, and fixes."""
    intended_behavior = intent_result.get("description", "Intent could not be determined.")
    actual_behavior = _summarize_actual_behavior(divergence)
    divergence_summary = "; ".join(divergence.get("causal_chain", [])) or "No divergences captured."
    first_div = divergence.get("first_divergence")
    root_cause = (
        first_div if isinstance(first_div, str) else "No divergence detected"
    )
    suggested_fix = _suggest_fix(divergence)
    base_confidence = intent_result.get("confidence", 0.5)
    score = divergence.get("score", 0.0)
    confidence = max(0.0, min(1.0, base_confidence * (1.0 - score)))

    base = {
        "intended_behavior": intended_behavior,
        "actual_behavior": actual_behavior,
        "divergence_summary": divergence_summary,
        "root_cause": root_cause,
        "suggested_fix": suggested_fix,
        "confidence": confidence,
    }
    refinements = _llm_reasoning(code, intent_result, divergence)
    if refinements:
        base.update(refinements)
    return base


def _llm_reasoning(
    code: str, intent_result: dict[str, Any], divergence: dict[str, Any]
) -> dict[str, Any]:
    """Use Anthropic to refine the reasoning narrative when available."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key or not divergence.get("mismatches"):
        return {}
    prompt = (
        f"{HUMAN_PROMPT}"
        "Given this Python code, describe the actual behavior, divergence summary, "
        "root cause, and suggested fix in JSON.\n"
        f"Code: {code}\n"
        f"Intent description: {intent_result.get('description', '')}\n"
        f"Divergence score: {divergence.get('score', 0.0)}\n"
        f"Causal chain: {', '.join(divergence.get('causal_chain', []))}\n"
        'Respond with JSON only: {"actual_behavior": str, "divergence_summary": str, '
        '"root_cause": str, "suggested_fix": str}\n'
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
        return {
            key: value
            for key, value in parsed.items()
            if key in {"actual_behavior", "divergence_summary", "root_cause", "suggested_fix"}
        }
    except Exception as exc:  # pragma: no cover - fallback
        logger.warning("Anthropic reasoning refinement failed: %s", exc)
        return {}
