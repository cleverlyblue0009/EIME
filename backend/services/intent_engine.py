from typing import Dict, List

from .ast_parser import parse_ast, DEFAULT_SNIPPET


def build_intent(code: str) -> List[Dict]:
    snippet = code.strip() or DEFAULT_SNIPPET
    summary = parse_ast(snippet)
    steps: List[Dict] = []

    step_id = 0

    summary_lines = [
        f"Function: {name}" for name in summary.get("functions", []) if name
    ]

    for line in summary_lines:
        steps.append(
            {
                "id": f"intent-{step_id}",
                "label": line,
                "line": None,
                "duration_ms": 8.0,
                "type": "intended",
                "variables": {},
            }
        )
        step_id += 1

    if summary.get("loops"):
        steps.append(
            {
                "id": f"intent-{step_id}",
                "label": "Loop-driven accumulation expected",
                "line": None,
                "duration_ms": 9.5,
                "type": "intended",
                "variables": {},
            }
        )
        step_id += 1

    if summary.get("recursive_calls"):
        steps.append(
            {
                "id": f"intent-{step_id}",
                "label": "Intent expects recursive unfolding",
                "line": None,
                "duration_ms": 10.4,
                "type": "intended",
                "variables": {},
            }
        )
        step_id += 1

    steps.append(
        {
            "id": f"intent-{step_id}",
            "label": "Result should return complete sequence up to limit",
            "line": None,
            "duration_ms": 7.2,
            "type": "intended",
            "variables": {"confidence": "high"},
        }
    )

    return steps
