import ast
from typing import Any


def _safe_literal_type(node: ast.AST) -> str:
    """Return the literal type name for a node when possible."""
    try:
        value = ast.literal_eval(node)
        return type(value).__name__
    except Exception:
        return "unknown"


def _node_source(code: str, node: ast.AST) -> str:
    """Return the source segment for a node, falling back to unparse."""
    try:
        return ast.get_source_segment(code, node) or ast.unparse(node)
    except Exception:
        return ast.unparse(node)


class _ParserVisitor(ast.NodeVisitor):
    def __init__(self, code: str) -> None:
        self.code = code
        self.functions: list[dict[str, Any]] = []
        self.loops: list[dict[str, Any]] = []
        self.variables: list[dict[str, Any]] = []
        self.conditionals: list[dict[str, Any]] = []
        self.returns: list[dict[str, Any]] = []
        self.calls: list[dict[str, Any]] = []
        self.has_recursion = False
        self._function_stack: list[str] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Collect metadata about function definitions."""
        arg_names = [arg.arg for arg in node.args.args]
        body_lines = sorted(
            {
                n.lineno
                for n in ast.walk(node)
                if hasattr(n, "lineno")
            }
        )
        self.functions.append(
            {
                "name": node.name,
                "args": arg_names,
                "lineno": node.lineno,
                "body_lines": body_lines,
            }
        )
        self._function_stack.append(node.name)
        self.generic_visit(node)
        self._function_stack.pop()

    def visit_For(self, node: ast.For) -> None:
        """Record for-loops and traverse them."""
        target = ast.unparse(node.target) if node.target is not None else None
        self.loops.append(
            {"type": "for", "lineno": node.lineno, "target": target}
        )
        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> None:
        """Record while-loops and traverse them."""
        self.loops.append(
            {"type": "while", "lineno": node.lineno, "target": None}
        )
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        """Record assignments as variables."""
        value_type = _safe_literal_type(node.value) if node.value else "unknown"
        for target in node.targets:
            if isinstance(target, ast.Name):
                self.variables.append(
                    {"name": target.id, "lineno": target.lineno, "value_type": value_type}
                )
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        """Record annotated assignments."""
        value_type = _safe_literal_type(node.value) if node.value else "unknown"
        target = node.target
        if isinstance(target, ast.Name):
            self.variables.append(
                {"name": target.id, "lineno": target.lineno, "value_type": value_type}
            )
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        """Record augmented assignments."""
        target = node.target
        if isinstance(target, ast.Name):
            self.variables.append(
                {
                    "name": target.id,
                    "lineno": target.lineno,
                    "value_type": _safe_literal_type(node.value)
                    if node.value
                    else "unknown",
                }
            )
        self.generic_visit(node)

    def visit_If(self, node: ast.If) -> None:
        """Record conditionals."""
        self.conditionals.append(
            {
                "lineno": node.lineno,
                "test_source": _node_source(self.code, node.test),
            }
        )
        self.generic_visit(node)

    def visit_Return(self, node: ast.Return) -> None:
        """Record return statements."""
        self.returns.append(
            {
                "lineno": node.lineno,
                "value_source": _node_source(self.code, node.value)
                if node.value
                else "None",
            }
        )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Record function calls and detect recursion."""
        func_name = _node_source(self.code, node.func)
        self.calls.append({"func": func_name, "lineno": node.lineno})
        if self._function_stack and func_name == self._function_stack[-1]:
            self.has_recursion = True
        self.generic_visit(node)


def parse_code(code: str) -> dict:
    """Parse Python code into an IR summary."""
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return {"error": str(exc)}

    visitor = _ParserVisitor(code)
    visitor.visit(tree)

    return {
        "functions": visitor.functions,
        "loops": visitor.loops,
        "variables": visitor.variables,
        "conditionals": visitor.conditionals,
        "returns": visitor.returns,
        "calls": visitor.calls,
        "has_recursion": visitor.has_recursion,
    }
