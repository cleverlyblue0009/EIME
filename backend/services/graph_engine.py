from __future__ import annotations

from typing import Any


def build_graph(
    execution_trace: list[dict[str, Any]],
    intent_trace: list[dict[str, Any]],
    mismatches: list[dict[str, Any]],
) -> dict[str, Any]:
    """Construct a D3-compatible graph of actual and intent steps."""
    truncated = False
    max_nodes = 200
    actual_steps = execution_trace
    if len(actual_steps) > max_nodes:
        truncated = True
        actual_steps = actual_steps[:max_nodes]

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    exec_node_by_step: dict[int, str] = {}
    divergence_steps: set[int] = {
        m["step"] for m in mismatches if m.get("step") is not None
    }

    for idx, entry in enumerate(actual_steps):
        step = entry.get("step", idx + 1)
        node_id = f"exec-{step}"
        node_type = "divergence" if step in divergence_steps else "actual"
        nodes.append(
            {
                "id": node_id,
                "label": f"{entry.get('func','<module>')}@{entry.get('line',0)}",
                "line": entry.get("line", 0) or 0,
                "type": node_type,
                "step": step,
            }
        )
        exec_node_by_step[step] = node_id

    for idx in range(len(actual_steps) - 1):
        edges.append(
            {
                "source": nodes[idx]["id"],
                "target": nodes[idx + 1]["id"],
                "type": "control_flow",
            }
        )

    intent_nodes: list[dict[str, Any]] = []
    intent_nodes_by_line: dict[int, list[str]] = {}
    for entry in intent_trace:
        node_id = f"intent-{entry.get('step', 0)}"
        intent_nodes.append(
            {
                "id": node_id,
                "label": f"intent@{entry.get('line', 0) or 0}",
                "line": entry.get("line", 0) or 0,
                "type": "intent",
                "step": entry.get("step", 0),
            }
        )
        intent_nodes_by_line.setdefault(entry.get("line", 0) or 0, []).append(node_id)

    nodes.extend(intent_nodes)

    seen_links: set[tuple[str, str]] = set()
    for mismatch in mismatches:
        actual_step = mismatch.get("step")
        line = mismatch.get("line", 0) or 0
        actual_id = exec_node_by_step.get(actual_step)
        if not actual_id:
            continue
        targets = intent_nodes_by_line.get(line, [])
        for target_id in targets:
            link = (actual_id, target_id)
            if link in seen_links:
                continue
            edges.append(
                {"source": actual_id, "target": target_id, "type": "divergence_link"}
            )
            seen_links.add(link)
            break

    return {
        "nodes": nodes,
        "edges": edges,
        "metadata": {
            "truncated": truncated,
            "total_steps": len(execution_trace),
        },
    }
