from __future__ import annotations

import ast
from typing import List

from backend.api.models import Divergence
from backend.divergence.classifiers.base_classifier import BaseClassifier


class DP1DClassifier(BaseClassifier):
    def applicable(self, intent) -> bool:
        return intent.inferred_algorithm.startswith("dp_1d")

    def detect(self, trace, intent, expectation, cfg) -> List[Divergence]:
        divergences: List[Divergence] = []
        source = self._source(cfg)

        if "climb_stairs" in source:
            base_case = self._find_line_containing(cfg, "dp[0] = 0", default=0)
            if base_case:
                divergences.append(
                    self._make_divergence(
                        divergence_type="WRONG_BASE_CASE_VALUE",
                        severity="HIGH",
                        line=base_case,
                        expected_behavior=(
                            "For climb-stairs counting, `dp[0]` should be 1 because there is one "
                            "way to stand at step 0 before taking any moves."
                        ),
                        actual_behavior="The base case initializes `dp[0]` to 0, so every later count is shifted down.",
                        algorithm_context=(
                            "1D DP is only correct if each recurrence builds on a semantically correct "
                            "base state."
                        ),
                        fix_suggestion=f"On line {base_case}, change the base case to `dp[0] = 1`.",
                        affected_variables=["dp"],
                    )
                )

        loop_bound = self._find_range_n_without_inclusive_end(cfg)
        if loop_bound is not None:
            line = getattr(loop_bound, "lineno", 1)
            divergences.append(
                self._make_divergence(
                    divergence_type="LOOP_BOUND_ERROR",
                    severity="MEDIUM",
                    line=line,
                    expected_behavior="The DP loop should build every state up to and including n.",
                    actual_behavior="The loop iterates with `range(n)`, which can stop one state early.",
                    algorithm_context=(
                        "1D DP relies on computing the full prefix of subproblems before the final "
                        "answer is returned."
                    ),
                    fix_suggestion="Use an inclusive bound such as `range(1, n + 1)` or `range(2, n + 1)`.",
                    affected_variables=["dp", "n"],
                )
            )

        wrong_return = self._find_wrong_dp_return(cfg)
        if wrong_return is not None:
            line = getattr(wrong_return, "lineno", 1)
            divergences.append(
                self._make_divergence(
                    divergence_type="WRONG_RETURN_VALUE",
                    severity="HIGH",
                    line=line,
                    expected_behavior="The final answer should come from the state that represents the full problem size.",
                    actual_behavior="The function returns `dp[n-1]`, which corresponds to a smaller subproblem.",
                    algorithm_context=(
                        "DP tables encode subproblem meaning by index, so an off-by-one return reads "
                        "the wrong semantic state."
                    ),
                    fix_suggestion=f"On line {line}, return `dp[n]` instead of `dp[n-1]`.",
                    affected_variables=["dp", "n"],
                )
            )

        return divergences

    def _find_range_n_without_inclusive_end(self, cfg) -> ast.For | None:
        for node in self._iter_nodes(cfg, ast.For):
            if not isinstance(node.iter, ast.Call):
                continue
            if not isinstance(node.iter.func, ast.Name) or node.iter.func.id != "range":
                continue
            text = self._ast_text(node.iter)
            if text in {"range(n)", "range(1, n)", "range(2, n)"}:
                return node
        return None

    def _find_wrong_dp_return(self, cfg) -> ast.Return | None:
        for node in self._iter_nodes(cfg, ast.Return):
            text = self._ast_text(node.value)
            if text in {"dp[n - 1]", "dp[n-1]"}:
                return node
        return None
