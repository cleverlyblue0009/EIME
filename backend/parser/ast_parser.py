import ast
from typing import Any, Dict, List, Set


def parse_code(code: str) -> Dict[str, Any]:
    try:
        tree = ast.parse(code)
        return {
            "ast": tree,
            "errors": None,
            "source": code,
        }
    except SyntaxError as exc:
        return {
            "ast": None,
            "errors": str(exc),
            "source": code,
        }


def collect_imports(tree: ast.AST) -> List[str]:
    imports: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
    return imports


def collect_var_names(tree: ast.AST) -> Set[str]:
    names: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
    return names


def collect_loops(tree: ast.AST) -> List[Dict[str, Any]]:
    loops: List[Dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.For, ast.While)):
            loop_var = None
            if isinstance(node, ast.For) and isinstance(node.target, ast.Name):
                loop_var = node.target.id
            loops.append(
                {
                    "header_line": getattr(node, "lineno", 0),
                    "end_line": getattr(node, "end_lineno", getattr(node, "lineno", 0)),
                    "loop_variable": loop_var,
                    "type": "for" if isinstance(node, ast.For) else "while",
                }
            )
    return loops


def build_line_index(tree: ast.AST, source: str) -> Dict[int, Dict[str, Any]]:
    source_lines = source.splitlines()
    statements = sorted(
        [node for node in ast.walk(tree) if isinstance(node, ast.stmt)],
        key=lambda node: (getattr(node, "lineno", 0), getattr(node, "col_offset", 0)),
    )

    index: Dict[int, Dict[str, Any]] = {}
    for node in statements:
        lineno = getattr(node, "lineno", None)
        if lineno is None or lineno <= 0 or lineno in index:
            continue
        index[lineno] = {
            "line_number": lineno,
            "code_line": source_lines[lineno - 1] if lineno - 1 < len(source_lines) else "",
            "operation": _statement_operation(node),
            "explanation": _statement_explanation(node),
            "reads": sorted(_read_names(node)),
            "writes": sorted(_write_names(node)),
            "read_accesses": sorted(_read_access_templates(node)),
            "write_accesses": sorted(_write_access_templates(node)),
            "condition": _condition_text(node),
        }
    return index


def _statement_operation(node: ast.stmt) -> str:
    if isinstance(node, (ast.For, ast.While)):
        return "loop_header"
    if isinstance(node, ast.If):
        return "branch"
    if isinstance(node, (ast.Assign, ast.AnnAssign)):
        return "assignment"
    if isinstance(node, ast.AugAssign):
        return "mutation"
    if isinstance(node, ast.Return):
        return "return"
    if isinstance(node, ast.FunctionDef):
        return "function_entry"
    if isinstance(node, ast.Expr) and isinstance(getattr(node, "value", None), ast.Call):
        return "call"
    return type(node).__name__.lower()


def _statement_explanation(node: ast.stmt) -> str:
    if isinstance(node, ast.For):
        return "Advance the loop by binding the next iterable value and entering the loop body."
    if isinstance(node, ast.While):
        return "Re-check the loop condition to decide whether the next iteration should execute."
    if isinstance(node, ast.If):
        return "Evaluate the branch condition and choose the next control-flow path."
    if isinstance(node, ast.Assign):
        return "Compute the right-hand side and store it into the assignment target."
    if isinstance(node, ast.AugAssign):
        return "Read the current target value, apply the update, and write the mutated value back."
    if isinstance(node, ast.Return):
        return "Finalize the current function frame and return the computed value."
    if isinstance(node, ast.FunctionDef):
        return "Define a function that may be invoked later during execution."
    if isinstance(node, ast.Expr) and isinstance(getattr(node, "value", None), ast.Call):
        return "Invoke a function for its side effects or produced value."
    return "Execute the statement and update program state accordingly."


def _read_names(node: ast.AST) -> Set[str]:
    names: Set[str] = set()
    for child in _relevant_read_roots(node):
        for grandchild in ast.walk(child):
            if isinstance(grandchild, ast.Name) and isinstance(grandchild.ctx, ast.Load):
                names.add(grandchild.id)
    return names


def _write_names(node: ast.AST) -> Set[str]:
    names: Set[str] = set()
    for target in _relevant_write_targets(node):
        names.update(_target_names(target))
    if isinstance(node, ast.FunctionDef):
        names.add(node.name)
    return names


def _target_names(target: ast.AST) -> Set[str]:
    names: Set[str] = set()
    if isinstance(target, ast.Name):
        names.add(target.id)
    elif isinstance(target, (ast.Tuple, ast.List)):
        for elt in target.elts:
            names.update(_target_names(elt))
    elif isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name):
        names.add(target.value.id)
    elif isinstance(target, ast.Attribute):
        names.add(ast.unparse(target))
    return names


def _read_access_templates(node: ast.AST) -> Set[str]:
    accesses: Set[str] = set()
    for child in _relevant_read_roots(node):
        for grandchild in ast.walk(child):
            if isinstance(grandchild, ast.Subscript) and isinstance(grandchild.ctx, ast.Load):
                accesses.add(ast.unparse(grandchild))
            elif isinstance(grandchild, ast.Attribute) and isinstance(grandchild.ctx, ast.Load):
                accesses.add(ast.unparse(grandchild))
            elif isinstance(grandchild, ast.Name) and isinstance(grandchild.ctx, ast.Load):
                accesses.add(grandchild.id)
    return accesses


def _write_access_templates(node: ast.AST) -> Set[str]:
    accesses: Set[str] = set()
    for target in _relevant_write_targets(node):
        accesses.update(_collect_target_templates(target))
    if isinstance(node, ast.FunctionDef):
        accesses.add(node.name)
    return accesses


def _relevant_read_roots(node: ast.AST) -> List[ast.AST]:
    if isinstance(node, ast.Assign):
        return [node.value]
    if isinstance(node, ast.AnnAssign):
        return [node.value] if node.value is not None else []
    if isinstance(node, ast.AugAssign):
        return [node.target, node.value]
    if isinstance(node, ast.Return):
        return [node.value] if node.value is not None else []
    if isinstance(node, ast.If):
        return [node.test]
    if isinstance(node, ast.While):
        return [node.test]
    if isinstance(node, ast.For):
        return [node.iter]
    if isinstance(node, ast.Expr):
        return [node.value]
    return []


def _relevant_write_targets(node: ast.AST) -> List[ast.AST]:
    if isinstance(node, ast.Assign):
        return list(node.targets)
    if isinstance(node, ast.AnnAssign):
        return [node.target]
    if isinstance(node, ast.AugAssign):
        return [node.target]
    if isinstance(node, ast.For):
        return [node.target]
    return []


def _collect_target_templates(target: ast.AST) -> Set[str]:
    templates: Set[str] = set()
    if isinstance(target, ast.Name):
        templates.add(target.id)
    elif isinstance(target, (ast.Tuple, ast.List)):
        for elt in target.elts:
            templates.update(_collect_target_templates(elt))
    elif isinstance(target, (ast.Subscript, ast.Attribute)):
        templates.add(ast.unparse(target))
    return templates


def _condition_text(node: ast.AST) -> str | None:
    if isinstance(node, ast.If):
        return ast.unparse(node.test)
    if isinstance(node, ast.While):
        return ast.unparse(node.test)
    if isinstance(node, ast.For):
        return ast.unparse(node.iter)
    return None
