from __future__ import annotations

from typing import Any, Dict, List

from backend.api.models import GraphEdge, GraphNode, LineRef, NodeDetail


def build_intent_graph(intent, intent_steps, alignment_map) -> Dict[str, Any]:
    nodes: List[GraphNode] = []
    edges: List[GraphEdge] = []

    alignment_by_intent: Dict[str, List[int]] = {}
    for entry in alignment_map:
        key = entry.intent_step_id if hasattr(entry, "intent_step_id") else entry.get("intent_step_id")
        step_id = entry.execution_step_id if hasattr(entry, "execution_step_id") else entry.get("execution_step_id")
        if key and step_id:
            alignment_by_intent.setdefault(key, []).append(step_id)

    for intent_step in intent_steps:
        nodes.append(
            GraphNode(
                id=intent_step.intent_step_id,
                type="intent",
                label=intent_step.label,
                detail=NodeDetail(
                    full_description=intent_step.description,
                    variable_snapshot={},
                    code_ref=LineRef(lineno=intent_step.start_line) if intent_step.start_line else None,
                    role_in_algorithm=intent_step.algorithm_role or "intent_step",
                    why_matters="Intent steps describe what the programmer likely meant to happen.",
                    invariants_checked=list(intent_step.invariants),
                    operation="intent",
                    code_line=None,
                    preview_variables={},
                    hover_summary=intent_step.description,
                    group_kind="intent",
                    is_divergence_path=False,
                    line_number=intent_step.start_line,
                    code_snippet=None,
                    variables={},
                    operation_type="intent",
                    zoom_levels=["function", "loop", "step"],
                    member_step_ids=list(alignment_by_intent.get(intent_step.intent_step_id, [])),
                    group_id=intent_step.intent_step_id,
                    editable_fields=[],
                    data_dependencies=[],
                    controls={"editable": False},
                    alignment_targets=[f"step_{item}" for item in alignment_by_intent.get(intent_step.intent_step_id, [])[:12]],
                ),
                position={"x": 0.0, "y": 0.0},
                visual_tier=0,
                collapsed=False,
                cluster_id="intent_graph",
            )
        )

    ordered_ids = [step.intent_step_id for step in intent_steps]
    for previous, current in zip(ordered_ids, ordered_ids[1:]):
        edges.append(
            GraphEdge(
                id=f"{previous}->{current}",
                source=previous,
                target=current,
                type="intent_alignment",
                label="intent flow",
                animated=False,
                weight=1.0,
                variables=[],
            )
        )

    return {
        "nodes": [node.model_dump() for node in nodes],
        "edges": [edge.model_dump() for edge in edges],
        "meta": {
            "graph_kind": "intent",
            "intent_step_ids": ordered_ids,
        },
        "source": None,
        "first_divergence": None,
    }
