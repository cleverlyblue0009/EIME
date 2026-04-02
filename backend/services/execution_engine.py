from typing import List, Dict

from .ast_parser import DEFAULT_SNIPPET


def run_execution(code: str) -> List[Dict]:
    snippet = code.strip() or DEFAULT_SNIPPET
    lines = snippet.splitlines()
    steps: List[Dict] = []
    accumulated = 0.0
    for idx, raw in enumerate(lines):
        stripped = raw.strip()
        if not stripped:
            continue
        accumulated += 5 + (len(stripped) * 0.3)
        step = {
            "id": f"exec-{idx}",
            "label": stripped,
            "line": idx + 1,
            "duration_ms": round(accumulated % 42 + 1, 2),
            "type": "actual",
            "variables": {"iteration": str(idx), "snapshot": f"{len(stripped)} chars"},
        }
        steps.append(step)
    if not steps:
        steps.append(
            {
                "id": "exec-empty",
                "label": "no executable statements detected",
                "line": None,
                "duration_ms": 0,
                "type": "actual",
                "variables": {},
            }
        )
    return steps
