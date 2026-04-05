from __future__ import annotations

import ast
import logging
import os
from typing import Any

from anthropic import Anthropic, HUMAN_PROMPT, AI_PROMPT

logger = logging.getLogger(__name__)


def _node_source(code: str, node: ast.AST) -> str:
    try:
        return ast.get_source_segment(code, node) or ast.unparse(node)
    except Exception:
        return ast.unparse(node)


class _IntentVisitor(ast.NodeVisitor):
    def __init__(self, code: str) -> None:
        self.code = code
        self.operations: list[dict[str, Any]] = []

    def _add(self, node: ast.AST, operation: str, description: str) -> None:
        line = getattr(node, "lineno", 0) or 0
        self.operations.append(
            {"line": line, "operation": operation, "description": description}
        )

    def visit_For(self, node: ast.For) -> None:
        self._add(
            node,
            "loop",
            f"Loop over {_node_source(self.code, node.iter)}",
        )
        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> None:
        self._add(node, "loop", f"While {_node_source(self.code, node.test)}")
        self.generic_visit(node)

    def visit_If(self, node: ast.If) -> None:
        condition = _node_source(self.code, node.test)
        self._add(node, "condition", f"If {condition}")
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        targets = ", ".join(_node_source(self.code, t) for t in node.targets)
        value = _node_source(self.code, node.value)
        self._add(node, "assignment", f"Set {targets} = {value}")
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        target = _node_source(self.code, node.target)
        value = _node_source(self.code, node.value)
        self._add(node, "assignment", f"Update {target} with {value}")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        func_source = _node_source(self.code, node.func)
        description = f"Call {func_source}"
        if isinstance(node.func, ast.Attribute):
            attr = node.func.attr
            base = _node_source(self.code, node.func.value)
            if attr == "append":
                arg = _node_source(self.code, node.args[0]) if node.args else "value"
                description = f"Append {arg} to {base}"
            elif attr == "extend":
                arg = _node_source(self.code, node.args[0]) if node.args else "values"
                description = f"Extend {base} with {arg}"
            elif attr == "pop":
                description = f"Pop from {base}"
            elif attr == "popleft":
                description = f"Queue pop left from {base}"
            elif attr == "push":
                description = f"Push into {base}"
        elif isinstance(node.func, ast.Name):
            if node.func.id in {"heappush", "heappop"}:
                description = f"Heap operation {node.func.id}"
        self._add(node, "call", description)
        self.generic_visit(node)

    def visit_Return(self, node: ast.Return) -> None:
        value = _node_source(self.code, node.value) if node.value else "None"
        self._add(node, "return", f"Return {value}")
        self.generic_visit(node)


def _pattern_confidence(label: str) -> float:
    mapping = {
        "filter_even_numbers": 0.9,
        "sequence_accumulation": 0.8,
        "sorting_algorithm": 0.75,
        "recursive_computation": 0.85,
        "tree_traversal": 0.8,
        "graph_traversal": 0.8,
        "priority_queue_operation": 0.75,
        "general_computation": 0.5,
    }
    return mapping.get(label, 0.5)


def _detect_pattern(code: str, ir: dict[str, Any]) -> tuple[str, str]:
    lowered = code.lower()
    normalized = "".join(lowered.split())

    if "heapq" in lowered or "heappush" in lowered or "heappop" in lowered:
        return (
            "priority_queue_operation",
            "The code manipulates a priority queue using heap operations.",
        )
    if "deque" in lowered and ("popleft" in lowered or "appendleft" in lowered):
        return (
            "graph_traversal",
            "The code uses a queue-like structure, suggesting breadth-first traversal.",
        )
    if ".append(" in lowered and ".pop(" in lowered and "stack" in lowered:
        return (
            "tree_traversal",
            "Stack-style operations suggest depth-first traversal.",
        )
    if "fib" in lowered or "a,b=b,a+b" in normalized:
        return (
            "fibonacci_sequence",
            "The code iterates over Fibonacci-style pair updates.",
        )
    if "%2==0" in normalized or "%2==0" in lowered:
        return (
            "filter_even_numbers",
            "The code filters even numbers based on a modulo check.",
        )
    if ir.get("has_recursion"):
        return (
            "recursive_computation",
            "A function is calling itself, indicating recursion.",
        )
    if ir.get("loops") and ".append(" in lowered:
        return (
            "sequence_accumulation",
            "A loop builds a collection through repeated append operations.",
        )
    return (
        "general_computation",
        "General computation with no specific pattern detected.",
    )


def _llm_refine_intent(code: str) -> tuple[str | None, str | None]:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None, None
    prompt = (
        f"{HUMAN_PROMPT}"
        "Explain the purpose of this code block in simple human terms.\n"
        f"Code: {code}\n"
        f"{AI_PROMPT}"
    )
    try:
        client = Anthropic(api_key=api_key)
        response = client.completions.create(
            model="claude-3.0",
            prompt=prompt,
            max_tokens_to_sample=120,
            temperature=0.2,
        )
        description = response.completion.strip()
        return "llm_refined", description
    except Exception as exc:  # pragma: no cover
        logger.warning("Anthropic intent refinement failed: %s", exc)
        return None, None


def analyze_intent(code: str, ir: dict[str, Any]) -> dict[str, Any]:
    """Produce a semantic intent label, description, and operation trace."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        tree = None

    operations: list[dict[str, Any]] = []
    if tree is not None:
        visitor = _IntentVisitor(code)
        visitor.visit(tree)
        operations = visitor.operations

    label, description = _detect_pattern(code, ir)
    confidence = _pattern_confidence(label)
    source = "rules"

    llm_label, llm_description = _llm_refine_intent(code)
    if llm_description:
        description = llm_description
        if llm_label:
            label = llm_label
        confidence = min(1.0, max(confidence, 0.7))
        source = "rules+llm"

    intent_trace = [
        {
            "step": idx + 1,
            "line": op["line"],
            "expected_state": op["description"],
            "expected_locals": {},
            "invariant": "len(result) == number of loop iterations"
            if label == "filter_even_numbers"
            else "",
        }
        for idx, op in enumerate(operations)
    ]

    return {
        "label": label,
        "description": description,
        "confidence": confidence,
        "source": source,
        "semantic_operations": operations,
        "intent_trace": intent_trace,
    }
