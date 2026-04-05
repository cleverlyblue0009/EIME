from __future__ import annotations

import ast
from typing import Any



def _node_source(code: str, node: ast.AST) -> str:
    try:
        return ast.get_source_segment(code, node) or ast.unparse(node)
    except Exception:
        return ast.unparse(node)


def _find_return_slices(code: str) -> list[dict[str, Any]]:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []

    slices: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Subscript):
            target = node.value.value
            if isinstance(target, ast.Name) and isinstance(node.value.slice, ast.Slice):
                slices.append(
                    {
                        "line": node.lineno,
                        "target": target.id,
                        "slice": node.value.slice,
                        "source": _node_source(code, node.value),
                    }
                )
    return slices


def _extract_loop_expectations(code: str) -> list[dict[str, Any]]:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []

    loops: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.For):
            if isinstance(node.iter, ast.Call) and isinstance(node.iter.func, ast.Name):
                if node.iter.func.id == "range":
                    loops.append(
                        {
                            "line": node.lineno,
                            "range_args": node.iter.args,
                            "source": _node_source(code, node.iter),
                        }
                    )
    return loops


def _collect_conditions(code: str) -> list[dict[str, Any]]:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []

    conditions: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            body_lines = {
                stmt.lineno for stmt in node.body if hasattr(stmt, "lineno")
            }
            orelse_lines = {
                stmt.lineno for stmt in node.orelse if hasattr(stmt, "lineno")
            }
            conditions.append(
                {
                    "line": node.lineno,
                    "test": node.test,
                    "body_lines": body_lines,
                    "orelse_lines": orelse_lines,
                }
            )
    return conditions


def _returns_in_loops(code: str) -> list[dict[str, Any]]:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []

    returns: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.For, ast.While)):
            for inner in ast.walk(node):
                if isinstance(inner, ast.Return):
                    returns.append(
                        {
                            "loop_line": node.lineno,
                            "return_line": inner.lineno,
                        }
                    )
    return returns


def _evaluate_range(range_args: list[ast.AST], locals_snapshot: dict[str, Any]) -> int | None:
    if not range_args:
        return None
    try:
        compiled = [
            eval(compile(ast.Expression(arg), "<range>", "eval"), {}, locals_snapshot)
            for arg in range_args
        ]
        if not all(isinstance(val, int) for val in compiled):
            return None
        return len(range(*compiled))
    except Exception:
        return None


def _collect_appends(semantic_trace: list[dict[str, Any]]) -> dict[str, list[Any]]:
    appended: dict[str, list[Any]] = {}
    for entry in semantic_trace:
        state_diff = entry.get("state_diff", {})
        for mutation in state_diff.get("mutations", []):
            if mutation.get("type") == "list_length_change" and mutation.get("delta", 0) > 0:
                variable = mutation.get("variable")
                if not variable:
                    continue
                appended.setdefault(variable, []).extend(mutation.get("added_items", []))
    return appended


def compute_divergence(
    execution_trace: list[dict[str, Any]],
    semantic_trace: list[dict[str, Any]],
    intent_result: dict[str, Any],
    code: str,
    ir: dict[str, Any],
) -> dict[str, Any]:
    mismatches: list[dict[str, Any]] = []

    appended_map = _collect_appends(semantic_trace)
    return_slices = _find_return_slices(code)
    loops = _extract_loop_expectations(code)
    loop_returns = _returns_in_loops(code)
    conditions = _collect_conditions(code)

    iteration_counts: dict[int, int] = {}
    for entry in semantic_trace:
        iteration_context = entry.get("state", {}).get("iteration_context", {})
        for line, count in iteration_context.items():
            iteration_counts[line] = max(iteration_counts.get(line, 0), count)

    locals_by_line: dict[int, dict[str, Any]] = {}
    for entry in semantic_trace:
        line = entry.get("line")
        if line and line not in locals_by_line:
            locals_by_line[line] = entry.get("locals", {})

    # Condition branch mismatches
    for idx, entry in enumerate(semantic_trace[:-1]):
        line = entry.get("line")
        if not line:
            continue
        matching = [c for c in conditions if c.get("line") == line]
        if not matching:
            continue
        condition = matching[0]
        test_expr = condition.get("test")
        locals_snapshot = entry.get("locals", {})
        try:
            condition_value = eval(
                compile(ast.Expression(test_expr), "<condition>", "eval"),
                {},
                locals_snapshot,
            )
        except Exception:
            continue
        next_line = semantic_trace[idx + 1].get("line")
        if condition_value and next_line not in condition.get("body_lines", set()):
            mismatches.append(
                {
                    "step": entry.get("step"),
                    "line": line,
                    "type": "branch_mismatch",
                    "expected": True,
                    "actual": condition_value,
                    "description": "Condition evaluated true but body was not executed.",
                }
            )
        if not condition_value and next_line in condition.get("body_lines", set()):
            mismatches.append(
                {
                    "step": entry.get("step"),
                    "line": line,
                    "type": "branch_mismatch",
                    "expected": False,
                    "actual": condition_value,
                    "description": "Condition evaluated false but body was executed.",
                }
            )

    # Loop divergence
    for loop in loops:
        line = loop.get("line")
        expected = _evaluate_range(loop.get("range_args", []), locals_by_line.get(line, {}))
        actual = iteration_counts.get(line)
        if expected is not None and actual is not None and expected != actual:
            mismatches.append(
                {
                    "step": None,
                    "line": line,
                    "type": "loop_count",
                    "expected": expected,
                    "actual": actual,
                    "description": f"Loop at line {line} executed {actual} times vs expected {expected}.",
                }
            )

    # Premature returns inside loops
    for loop_return in loop_returns:
        loop_line = loop_return.get("loop_line")
        return_line = loop_return.get("return_line")
        expected = None
        for loop in loops:
            if loop.get("line") == loop_line:
                expected = _evaluate_range(loop.get("range_args", []), locals_by_line.get(loop_line, {}))
                break
        actual = iteration_counts.get(loop_line)
        if expected is not None and actual is not None and actual < expected:
            mismatches.append(
                {
                    "step": None,
                    "line": return_line,
                    "type": "premature_return",
                    "expected": expected,
                    "actual": actual,
                    "description": "Return executed before loop completed expected iterations.",
                }
            )

    # Return slicing divergence
    for ret in return_slices:
        line = ret.get("line")
        target = ret.get("target")
        if not target:
            continue
        appended_values = appended_map.get(target, [])
        for entry in execution_trace:
            if entry.get("event") == "return" and entry.get("line") == line:
                returned = entry.get("value")
                if isinstance(returned, list) and appended_values:
                    if len(returned) < len(appended_values):
                        mismatches.append(
                            {
                                "step": entry.get("step"),
                                "line": line,
                                "type": "missing_element",
                                "expected": appended_values,
                                "actual": returned,
                                "description": "Returned list is missing elements from appended values.",
                            }
                        )
                    if ret.get("source"):
                        mismatches.append(
                            {
                                "step": entry.get("step"),
                                "line": line,
                                "type": "output_slice",
                                "expected": appended_values,
                                "actual": returned,
                                "description": f"Return slices list at line {line}: {ret.get('source')}",
                            }
                        )

    # Output mismatch for list builders
    for variable, appended_values in appended_map.items():
        for entry in execution_trace:
            if entry.get("event") == "return":
                returned = entry.get("value")
                if isinstance(returned, list):
                    if len(returned) < len(appended_values):
                        mismatches.append(
                            {
                                "step": entry.get("step"),
                                "line": entry.get("line"),
                                "type": "missing_element",
                                "expected": appended_values,
                                "actual": returned,
                                "description": f"Output missing elements compared to {variable} append history.",
                            }
                        )
                    if len(returned) > len(appended_values):
                        mismatches.append(
                            {
                                "step": entry.get("step"),
                                "line": entry.get("line"),
                                "type": "extra_element",
                                "expected": appended_values,
                                "actual": returned,
                                "description": f"Output contains extra elements not appended to {variable}.",
                            }
                        )
                break

    # State inconsistency
    for entry in semantic_trace:
        state_diff = entry.get("state_diff", {})
        for mutation in state_diff.get("mutations", []):
            if mutation.get("type") == "list_length_change" and mutation.get("delta", 0) < 0:
                mismatches.append(
                    {
                        "step": entry.get("step"),
                        "line": entry.get("line"),
                        "type": "state_inconsistency",
                        "expected": None,
                        "actual": mutation,
                        "description": f"List {mutation.get('variable')} shrank unexpectedly.",
                    }
                )

    # Deduplicate mismatches
    unique: list[dict[str, Any]] = []
    seen_keys: set[tuple[Any, Any, Any, Any]] = set()
    for mismatch in mismatches:
        key = (
            mismatch.get("type"),
            mismatch.get("line"),
            mismatch.get("step"),
            mismatch.get("description"),
        )
        if key in seen_keys:
            continue
        seen_keys.add(key)
        unique.append(mismatch)

    mismatches = unique

    total_steps = len(execution_trace)
    score = min(len(mismatches) / max(total_steps, 1), 1.0)
    if score < 0.3:
        severity = "LOW"
    elif score < 0.7:
        severity = "MEDIUM"
    else:
        severity = "HIGH"

    first_divergence = None
    if mismatches:
        earliest = min(
            [m for m in mismatches if m.get("step") is not None] or mismatches,
            key=lambda entry: entry.get("step") or 0,
        )
        first_divergence = earliest.get("description", "Unknown divergence")

    seen_descriptions: set[str] = set()
    causal_chain: list[str] = []
    for mismatch in mismatches:
        desc = mismatch.get("description", "")
        if desc and desc not in seen_descriptions and len(causal_chain) < 6:
            seen_descriptions.add(desc)
            causal_chain.append(desc)

    return {
        "mismatches": mismatches,
        "first_divergence": first_divergence,
        "score": score,
        "severity": severity,
        "causal_chain": causal_chain,
        "total_steps": total_steps,
        "aligned_steps": max(total_steps - len(mismatches), 0),
    }
