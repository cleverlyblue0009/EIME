from __future__ import annotations

from typing import Any


def _summarize_diff(state_diff: dict[str, Any]) -> str:
    parts: list[str] = []
    if state_diff.get("added"):
        parts.append(f"Added {', '.join(state_diff['added'].keys())}")
    if state_diff.get("changed"):
        parts.append(f"Changed {', '.join(state_diff['changed'].keys())}")
    for mutation in state_diff.get("mutations", []):
        if mutation.get("type") == "list_length_change":
            parts.append(
                f"{mutation.get('variable')} length {mutation.get('from')}→{mutation.get('to')}"
            )
    return "; ".join(parts) if parts else "State unchanged."


def _semantic_label(entry: dict[str, Any], intent_ops: dict[int, str]) -> tuple[str, str]:
    line = entry.get("line")
    event = entry.get("event")
    state_diff = entry.get("state_diff", {})

    if line in intent_ops:
        label = intent_ops[line]
        return label, label

    for mutation in state_diff.get("mutations", []):
        if mutation.get("type") == "list_length_change" and mutation.get("delta", 0) > 0:
            variable = mutation.get("variable")
            added = mutation.get("added_items", [])
            if added:
                return (
                    f"Append {added[-1]} to {variable}",
                    f"Appended {added[-1]} to {variable}",
                )
            return (
                f"Append item to {variable}",
                f"Appended new item to {variable}",
            )

    if event == "return":
        return "Return result", "Return from function"
    if event == "call":
        return "Call function", "Entered function call"
    if event == "exception":
        return "Exception raised", "An exception interrupted execution"
    if event == "line":
        return f"Execute line {line}", f"Executed line {line}"

    return "Execution step", "Execution step"


def build_graph(
    semantic_trace: list[dict[str, Any]],
    intent_result: dict[str, Any],
    divergence: dict[str, Any],
) -> dict[str, Any]:
    intent_ops = {
        op.get("line"): op.get("description")
        for op in intent_result.get("semantic_operations", [])
        if op.get("line")
    }

    divergence_lines = {m.get("line") for m in divergence.get("mismatches", []) if m.get("line")}
    divergence_steps = {m.get("step") for m in divergence.get("mismatches", []) if m.get("step")}

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    previous_id: str | None = None
    for entry in semantic_trace:
        step = entry.get("step")
        node_id = f"exec-{step}"
        line = entry.get("line") or 0
        label, description = _semantic_label(entry, intent_ops)
        diff_summary = _summarize_diff(entry.get("state_diff", {}))
        if diff_summary and diff_summary != "State unchanged.":
            description = f"{description}. {diff_summary}"

        node_type = "actual"
        if step in divergence_steps or line in divergence_lines:
            node_type = "divergence"

        node = {
            "id": node_id,
            "type": node_type,
            "title": label,
            "description": description,
            "line_number": line,
            "function": entry.get("func") or "<module>",
            "variables": entry.get("locals", {}),
            "state_diff": entry.get("state_diff", {}),
            "iteration": entry.get("iteration"),
            "children": [],
        }
        nodes.append(node)

        if previous_id:
            edges.append(
                {"source": previous_id, "target": node_id, "type": "control_flow"}
            )
        previous_id = node_id

    intent_nodes: list[dict[str, Any]] = []
    for idx, op in enumerate(intent_result.get("semantic_operations", [])):
        intent_nodes.append(
            {
                "id": f"intent-{idx+1}",
                "type": "intended",
                "title": op.get("description"),
                "description": op.get("description"),
                "line_number": op.get("line") or 0,
                "function": "intent",
                "variables": {},
                "state_diff": {},
                "iteration": None,
                "children": [],
            }
        )
    nodes.extend(intent_nodes)

    for idx in range(1, len(intent_nodes)):
        edges.append(
            {
                "source": intent_nodes[idx - 1]["id"],
                "target": intent_nodes[idx]["id"],
                "type": "intent_flow",
            }
        )

    # Divergence links: connect actual to intent nodes with matching line
    line_to_intent = {
        node["line_number"]: node["id"]
        for node in intent_nodes
        if node.get("line_number")
    }
    for mismatch in divergence.get("mismatches", []):
        line = mismatch.get("line")
        step = mismatch.get("step")
        if line and step:
            target_id = line_to_intent.get(line)
            if target_id:
                edges.append(
                    {
                        "source": f"exec-{step}",
                        "target": target_id,
                        "type": "divergence",
                    }
                )

    return {
        "nodes": nodes,
        "edges": edges,
    }
