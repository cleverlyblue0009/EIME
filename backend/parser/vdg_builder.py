import ast
from typing import Any, Dict, List


def _collect_names(node: ast.AST) -> List[str]:
    names: List[str] = []
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            names.append(child.id)
    return names


def build_vdg(tree: ast.AST) -> Dict[str, Any]:
    if tree is None:
        return {"dependencies": {}, "usage": {}}

    dependencies: Dict[str, List[str]] = {}
    usage: Dict[str, List[int]] = {}

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            value_names = _collect_names(node.value)
            for target in node.targets:
                if isinstance(target, ast.Name):
                    dependencies.setdefault(target.id, []).extend(value_names)
        elif isinstance(node, ast.AugAssign):
            if isinstance(node.target, ast.Name):
                dependencies.setdefault(node.target.id, []).extend(_collect_names(node.value))

        if isinstance(node, ast.Name) and hasattr(node, "lineno"):
            usage.setdefault(node.id, []).append(node.lineno)

    return {"dependencies": dependencies, "usage": usage}
