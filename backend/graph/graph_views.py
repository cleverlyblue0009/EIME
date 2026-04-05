from __future__ import annotations

from typing import Any, Dict, Iterable


def build_execution_view(hybrid_graph: Dict[str, Any]) -> Dict[str, Any]:
    return _filter_graph(
        hybrid_graph,
        allowed_node_types={
            "execution",
            "function_entry",
            "function_exit",
            "loop_header",
            "loop_iteration",
            "loop_exit",
            "recursion_call",
            "recursion_base",
            "divergence",
        },
        allowed_edge_types={
            "control_flow",
            "call",
            "return",
            "loop_back",
            "loop_exit",
            "branch_true",
            "branch_false",
            "intent_violation",
            "recursive_call",
            "memoized_return",
        },
        graph_kind="execution",
    )


def build_data_flow_view(hybrid_graph: Dict[str, Any]) -> Dict[str, Any]:
    return _filter_graph(
        hybrid_graph,
        allowed_node_types={
            "execution",
            "function_entry",
            "function_exit",
            "loop_header",
            "loop_iteration",
            "recursion_call",
            "recursion_base",
            "divergence",
        },
        allowed_edge_types={"data_flow", "dependency", "mutation", "intent_violation"},
        graph_kind="data_flow",
    )


def _filter_graph(
    hybrid_graph: Dict[str, Any],
    *,
    allowed_node_types: Iterable[str],
    allowed_edge_types: Iterable[str],
    graph_kind: str,
) -> Dict[str, Any]:
    node_type_set = set(allowed_node_types)
    edge_type_set = set(allowed_edge_types)

    nodes = [node for node in hybrid_graph.get("nodes", []) if node.get("type") in node_type_set]
    visible_node_ids = {node["id"] for node in nodes}
    edges = [
        edge
        for edge in hybrid_graph.get("edges", [])
        if edge.get("type") in edge_type_set
        and edge.get("source") in visible_node_ids
        and edge.get("target") in visible_node_ids
    ]

    meta = dict(hybrid_graph.get("meta", {}))
    meta["graph_kind"] = graph_kind
    return {
        "nodes": nodes,
        "edges": edges,
        "meta": meta,
        "source": hybrid_graph.get("source"),
        "first_divergence": hybrid_graph.get("first_divergence"),
    }
