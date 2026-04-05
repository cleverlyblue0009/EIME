import ast
from typing import Any, Dict, List


def build_cfg(tree: ast.AST) -> Dict[str, Any]:
    if tree is None:
        return {"nodes": [], "edges": [], "entry": None, "exit": None}

    line_numbers: List[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.stmt) and hasattr(node, "lineno"):
            line_numbers.append(node.lineno)
    line_numbers = sorted(set(line_numbers))

    nodes = [{"id": f"bb-{i}", "lineno": ln} for i, ln in enumerate(line_numbers)]
    edges = []
    for i in range(len(nodes) - 1):
        edges.append({"source": nodes[i]["id"], "target": nodes[i + 1]["id"]})

    return {
        "nodes": nodes,
        "edges": edges,
        "entry": nodes[0]["id"] if nodes else None,
        "exit": nodes[-1]["id"] if nodes else None,
    }
