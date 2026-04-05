from __future__ import annotations

from typing import Any, Dict

from backend.reasoning.llm_reasoner import analyze_reasoning_with_llm


def suggest_intent(code: str, api_key: str | None = None) -> Dict[str, Any]:
    result = analyze_reasoning_with_llm(
        code=code,
        trace_summary={},
        divergence_summary={},
        structural_intent={"algorithm": None, "variant": None, "goal": None},
        api_key=api_key,
    )
    return {
        "hint": result.get("human_explanation") or result.get("intended_behavior") or "",
        "confidence": 0.78 if result.get("algorithm_type") else 0.0,
        "algorithm_type": result.get("algorithm_type"),
        "raw": result,
    }
