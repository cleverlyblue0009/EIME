import ast
from typing import Any, Dict, List


def build_call_graph(tree: ast.AST) -> Dict[str, Any]:
    if tree is None:
        return {"calls": {}, "recursive_lines": []}

    calls: Dict[str, List[str]] = {}
    recursive_lines: List[int] = []
    current_func = "<module>"

    class CallVisitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
            nonlocal current_func
            prev = current_func
            current_func = node.name
            self.generic_visit(node)
            current_func = prev

        def visit_Call(self, node: ast.Call) -> Any:
            name = None
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
            if name:
                calls.setdefault(current_func, []).append(name)
                if current_func == name and getattr(node, "lineno", 0):
                    recursive_lines.append(node.lineno)
            self.generic_visit(node)

    CallVisitor().visit(tree)
    return {"calls": calls, "recursive_lines": sorted(set(recursive_lines))}
