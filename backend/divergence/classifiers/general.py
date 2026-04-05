from __future__ import annotations

import ast
from typing import List

from backend.api.models import Divergence
from backend.divergence.classifiers.base_classifier import BaseClassifier


class GeneralClassifier(BaseClassifier):
    def applicable(self, intent) -> bool:
        return True

    def detect(self, trace, intent, expectation, cfg) -> List[Divergence]:
        divergences: List[Divergence] = []

        if intent.inferred_algorithm not in {"sliding_window_fixed", "binary_search_array", "dp_1d_linear"}:
            off_by_one = self._find_generic_range_off_by_one(cfg)
            if off_by_one is not None:
                line = getattr(off_by_one, "lineno", 1)
                divergences.append(
                    self._make_divergence(
                        divergence_type="OFF_BY_ONE",
                        severity="MEDIUM",
                        line=line,
                        expected_behavior="Loop bounds should include every required case exactly once.",
                        actual_behavior="The loop upper bound subtracts one from a length-based limit and risks skipping the final case.",
                        algorithm_context=(
                            "Off-by-one bounds usually mean the implementation stops one iteration "
                            "before the intended invariant has covered the full input."
                        ),
                        fix_suggestion="Re-check whether the upper bound should be inclusive and add `+ 1` when needed.",
                    )
                )

        if intent.inferred_algorithm in {"interval_merge", "graph_mst", "greedy"}:
            comparator_line = self._find_sort_without_key(cfg)
            if comparator_line is not None:
                divergences.append(
                    self._make_divergence(
                        divergence_type="WRONG_COMPARATOR",
                        severity="MEDIUM",
                        line=comparator_line,
                        expected_behavior="The algorithm should sort using the semantic key that defines the greedy or merge order.",
                        actual_behavior="Sorting is performed without an explicit key, so tuple ordering or raw object order decides the outcome.",
                        algorithm_context=(
                            "Order-sensitive algorithms are only correct when elements are ranked by "
                            "the exact comparison the invariant depends on."
                        ),
                        fix_suggestion="Provide an explicit `key=` function that sorts by the intended field.",
                    )
                )

        if intent.inferred_algorithm not in {
            "binary_search_array",
            "bfs_standard",
            "bfs_level_order",
            "dfs_recursive",
            "dfs_iterative",
            "backtracking",
            "recursion_memo",
            "merge_sort",
            "quick_sort_lomuto",
        }:
            early_return = self._find_return_inside_loop(cfg)
            if early_return is not None:
                line = getattr(early_return, "lineno", 1)
                divergences.append(
                    self._make_divergence(
                        divergence_type="EARLY_RETURN",
                        severity="LOW",
                        line=line,
                        expected_behavior="The algorithm should finish evaluating all required cases before returning the aggregate result.",
                        actual_behavior="A return statement appears inside the main loop and may terminate evaluation before all cases are processed.",
                        algorithm_context=(
                            "Aggregation-style algorithms usually need the full traversal before the "
                            "result is semantically complete."
                        ),
                        fix_suggestion="Move the return outside the loop unless the algorithm is intentionally short-circuiting.",
                    )
                )

        null_check = self._find_missing_null_check(cfg)
        if null_check is not None:
            divergences.append(
                self._make_divergence(
                    divergence_type="MISSING_NULL_CHECK",
                    severity="HIGH",
                    line=null_check,
                    expected_behavior="Pointer-based traversals should guard node references before dereferencing `.next`, `.left`, or `.right`.",
                    actual_behavior="Attribute access on a likely node pointer appears without a clear null/None guard.",
                    algorithm_context=(
                        "Linked-list and tree invariants start with safe pointer validity. Missing that "
                        "guard can crash traversal before algorithm logic even runs."
                    ),
                    fix_suggestion="Add a guard such as `if node is None:` or `while current is not None:` before dereferencing the pointer.",
                )
            )

        return divergences

    def _find_generic_range_off_by_one(self, cfg) -> ast.For | None:
        for node in self._iter_nodes(cfg, ast.For):
            if not isinstance(node.iter, ast.Call):
                continue
            if not isinstance(node.iter.func, ast.Name) or node.iter.func.id != "range":
                continue
            text = self._ast_text(node.iter)
            if "len(" in text and any(token in text for token in {"- 1", "-1"}) and "+ 1" not in text:
                return node
        return None

    def _find_sort_without_key(self, cfg) -> int | None:
        for node in self._iter_nodes(cfg, ast.Call):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name) and node.func.id == "sorted":
                if not any(keyword.arg == "key" for keyword in node.keywords):
                    return getattr(node, "lineno", 1)
            if isinstance(node.func, ast.Attribute) and node.func.attr == "sort":
                if not any(keyword.arg == "key" for keyword in node.keywords):
                    return getattr(node, "lineno", 1)
        return None

    def _find_return_inside_loop(self, cfg) -> ast.Return | None:
        for loop in self._iter_nodes(cfg, (ast.For, ast.While)):
            for node in ast.walk(loop):
                if isinstance(node, ast.Return):
                    return node
        return None

    def _find_missing_null_check(self, cfg) -> int | None:
        source = self._source(cfg)
        if not any(token in source for token in {".next", ".left", ".right"}):
            return None

        has_guard = any(
            token in source
            for token in {
                " is None",
                " is not None",
                "if not ",
                "while current",
                "while curr",
                "while node",
                "while head",
                "if current",
                "if curr",
                "if head",
            }
        )
        if has_guard:
            return None

        return self._find_line_containing(cfg, ".next", default=self._find_line_containing(cfg, ".left", default=1))
