from __future__ import annotations

import ast
from typing import List, Set

from backend.api.models import Divergence
from backend.divergence.classifiers.base_classifier import BaseClassifier


class RecursionMemoClassifier(BaseClassifier):
    def applicable(self, intent) -> bool:
        return intent.inferred_algorithm == "recursion_memo"

    def detect(self, trace, intent, expectation, cfg) -> List[Divergence]:
        divergences: List[Divergence] = []
        function = self._recursive_function(cfg)
        if function is None:
            return divergences

        if not self._has_base_case(function):
            line = getattr(function, "lineno", 1)
            divergences.append(
                self._make_divergence(
                    divergence_type="BASE_CASE_MISSING",
                    severity="CRITICAL",
                    line=line,
                    expected_behavior="Recursive algorithms must stop on their smallest valid subproblem.",
                    actual_behavior="No non-recursive base case was detected in the recursive function.",
                    algorithm_context=(
                        "Without a base case, the recursion tree has no terminating leaves and cannot "
                        "model the intended subproblem structure."
                    ),
                    fix_suggestion="Add a base case such as `if n <= 1: return n` before recursive calls.",
                )
            )

        wrong_base_case = self._wrong_known_base_case(function)
        if wrong_base_case is not None:
            line = getattr(wrong_base_case, "lineno", 1)
            divergences.append(
                self._make_divergence(
                    divergence_type="WRONG_BASE_CASE_VALUE",
                    severity="CRITICAL",
                    line=line,
                    expected_behavior="The base case should return the identity value required by the recurrence.",
                    actual_behavior="The base case returns a value that contradicts the recurrence definition.",
                    algorithm_context=(
                        "Recursive correctness starts at the leaves; a wrong base value poisons every "
                        "parent computation built on top of it."
                    ),
                    fix_suggestion=(
                        "Adjust the base case value so it matches the recurrence, for example "
                        "`factorial(0) -> 1` or `fib(0) -> 0, fib(1) -> 1`."
                    ),
                )
            )

        if self._has_memo_structure(function) and not self._checks_memo_before_recursing(function):
            line = getattr(function, "lineno", 1)
            divergences.append(
                self._make_divergence(
                    divergence_type="MEMOIZATION_MISS",
                    severity="HIGH",
                    line=line,
                    expected_behavior="Memoized recursion should consult the cache before expanding subproblems.",
                    actual_behavior="A memo/cache structure exists, but there is no guard that returns a cached answer before recursion.",
                    algorithm_context=(
                        "Memoization turns repeated subtrees into constant-time lookups. Skipping the "
                        "cache check preserves the exponential recursion shape."
                    ),
                    fix_suggestion="Add `if key in memo: return memo[key]` before the recursive calls.",
                    affected_variables=["memo", "cache"],
                )
            )

        if self._has_non_reducing_recursive_call(function):
            line = self._find_line_containing(cfg, f"{function.name}(", default=getattr(function, "lineno", 1))
            divergences.append(
                self._make_divergence(
                    divergence_type="INVARIANT_VIOLATION",
                    severity="HIGH",
                    line=line,
                    expected_behavior="Each recursive call should move to a strictly smaller subproblem.",
                    actual_behavior="At least one recursive call reuses the same state instead of reducing it.",
                    algorithm_context=(
                        "Recursive algorithms rely on well-founded descent; without reduction, the "
                        "call tree can loop forever."
                    ),
                    fix_suggestion="Pass a smaller state into recursion, such as `n - 1`, `lo + 1`, or a smaller slice.",
                )
            )

        if self._drops_one_recursive_half(function):
            line = getattr(function, "lineno", 1)
            divergences.append(
                self._make_divergence(
                    divergence_type="WRONG_RECURSIVE_RETURN",
                    severity="HIGH",
                    line=line,
                    expected_behavior="Divide-and-conquer recursion should combine every recursive branch required by the recurrence.",
                    actual_behavior="The function makes multiple recursive calls but only returns one branch directly.",
                    algorithm_context=(
                        "The merge/combine step is the semantic glue of divide-and-conquer recursion. "
                        "Dropping one branch changes the problem being solved."
                    ),
                    fix_suggestion="Capture both recursive results and combine them according to the recurrence before returning.",
                )
            )

        return divergences

    def _recursive_function(self, cfg) -> ast.FunctionDef | None:
        for function in self._iter_nodes(cfg, ast.FunctionDef):
            if not isinstance(function, ast.FunctionDef):
                continue
            if any(
                isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == function.name
                for call in ast.walk(function)
            ):
                return function
        return None

    def _has_base_case(self, function: ast.FunctionDef) -> bool:
        for stmt in function.body:
            if isinstance(stmt, ast.If):
                has_return = any(isinstance(child, ast.Return) for child in stmt.body)
                has_recursive_call = any(
                    isinstance(child, ast.Call) and isinstance(child.func, ast.Name) and child.func.id == function.name
                    for child in ast.walk(stmt)
                )
                if has_return and not has_recursive_call:
                    return True
        return False

    def _wrong_known_base_case(self, function: ast.FunctionDef) -> ast.Return | None:
        for stmt in ast.walk(function):
            if not isinstance(stmt, ast.If):
                continue
            condition = self._ast_text(stmt.test)
            for child in stmt.body:
                if not isinstance(child, ast.Return):
                    continue
                value = self._ast_text(child.value)
                if "factorial" in function.name and ("== 0" in condition or "<= 1" in condition) and value == "0":
                    return child
        return None

    def _has_memo_structure(self, function: ast.FunctionDef) -> bool:
        text = self._ast_text(function)
        return any(token in text for token in {"memo", "cache", "lru_cache"})

    def _checks_memo_before_recursing(self, function: ast.FunctionDef) -> bool:
        text = self._ast_text(function)
        return "in memo" in text or "in cache" in text or "@lru_cache" in text

    def _has_non_reducing_recursive_call(self, function: ast.FunctionDef) -> bool:
        params = [
            arg.arg
            for arg in function.args.args
            if arg.arg not in {"memo", "cache", "dp", "table", "lookup"}
        ]
        for call in ast.walk(function):
            if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Name) or call.func.id != function.name:
                continue
            compared_args = call.args[: len(params)]
            if compared_args and len(compared_args) == len(params):
                if all(isinstance(arg, ast.Name) and arg.id == param for arg, param in zip(compared_args, params)):
                    return True
        return False

    def _drops_one_recursive_half(self, function: ast.FunctionDef) -> bool:
        recursive_calls = [
            call
            for call in ast.walk(function)
            if isinstance(call, ast.Call)
            and isinstance(call.func, ast.Name)
            and call.func.id == function.name
        ]
        if len(recursive_calls) < 2:
            return False

        for node in ast.walk(function):
            if not isinstance(node, ast.Return):
                continue
            if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name):
                if node.value.func.id == function.name:
                    return True
        return False
