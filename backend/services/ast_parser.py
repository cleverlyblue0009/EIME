import ast
from typing import Dict, List

DEFAULT_SNIPPET = """from functools import lru_cache

@lru_cache(maxsize=None)
def compute_sequence(limit: int):
    if limit <= 0:
        return []
    sequence = []
    prev, curr = 0, 1
    while len(sequence) < limit:
        sequence.append(prev)
        prev, curr = curr, prev + curr
    return sequence
"""


def parse_ast(code: str) -> Dict[str, List[str]]:
    snippet = code.strip() or DEFAULT_SNIPPET
    try:
        tree = ast.parse(snippet)
    except SyntaxError:
        return {"functions": [], "loops": [], "recursive_calls": []}

    functions: List[str] = []
    loops: List[str] = []
    recursive_calls: List[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            functions.append(node.name)
            if any(
                isinstance(child, ast.Call)
                and getattr(child.func, "id", "") == node.name
                for child in ast.walk(node)
            ):
                recursive_calls.append(node.name)
        if isinstance(node, (ast.For, ast.While, ast.AsyncFor)):
            loops.append(type(node).__name__)

    return {"functions": functions, "loops": loops, "recursive_calls": recursive_calls}
