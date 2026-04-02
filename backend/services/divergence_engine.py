from typing import Dict, List


def detect_divergence(
    execution_trace: List[Dict], intent_trace: List[Dict]
) -> Dict:
    first_divergence = None
    for exec_step, intent_step in zip(execution_trace, intent_trace):
        if exec_step["label"] != intent_step["label"]:
            first_divergence = exec_step
            break
    if not first_divergence and execution_trace:
        first_divergence = execution_trace[-1]

    length_delta = abs(len(execution_trace) - len(intent_trace))
    score = round(max(0.35, 1 - length_delta * 0.15), 2)
    severity = "HIGH" if length_delta >= 2 else "MEDIUM"

    if not first_divergence:
        first_divergence = {
            "id": "exec-missing",
            "label": "No divergence detected",
            "line": None,
        }

    causal_chain = [
        f"Execution path diverges around '{first_divergence['label']}'",
        "Intent model predicted a complete range, but execution stopped early",
    ]

    return {
        "first_divergence": first_divergence["label"],
        "first_divergence_node": f"node-{first_divergence['id']}",
        "score": score,
        "severity": severity,
        "confidence": score,
        "causal_chain": causal_chain,
        "highlights": [first_divergence["id"]],
    }


def build_graph_payload(
    execution_trace: List[Dict], intent_trace: List[Dict], divergence: Dict
) -> Dict:
    nodes: List[Dict] = [
        {
            "id": "node-start",
            "label": "Start",
            "type": "meta",
            "status": "active",
            "highlight": False,
        },
        {
            "id": "node-intent",
            "label": "Intended Flow",
            "type": "intended",
            "status": "stable",
            "highlight": False,
        },
        {
            "id": "node-actual",
            "label": "Actual Flow",
            "type": "actual",
            "status": "running",
            "highlight": False,
        },
    ]

    divergence_node_id = divergence.get("first_divergence_node", "node-divergence")
    nodes.append(
        {
            "id": divergence_node_id,
            "label": "FIRST DIVERGENCE",
            "type": "divergence",
            "status": "critical",
            "highlight": True,
        }
    )

    edges: List[Dict] = [
        {
            "id": "edge-start-intent",
            "source": "node-start",
            "target": "node-intent",
            "type": "intended",
            "highlight": False,
        },
        {
            "id": "edge-start-actual",
            "source": "node-start",
            "target": "node-actual",
            "type": "actual",
            "highlight": False,
        },
        {
            "id": "edge-actual-divergence",
            "source": "node-actual",
            "target": divergence_node_id,
            "type": "divergence",
            "highlight": True,
        },
    ]

    edges.append(
        {
            "id": "edge-intent-divergence",
            "source": "node-intent",
            "target": divergence_node_id,
            "type": "intended",
            "highlight": False,
        }
    )

    return {
        "nodes": nodes,
        "edges": edges,
        "first_divergence": divergence_node_id,
    }
