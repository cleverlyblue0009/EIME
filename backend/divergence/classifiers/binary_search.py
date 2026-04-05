from __future__ import annotations

import ast
from typing import List

from backend.api.models import Divergence
from backend.divergence.classifiers.base_classifier import BaseClassifier


class BinarySearchClassifier(BaseClassifier):
    def applicable(self, intent) -> bool:
        return intent.inferred_algorithm in {"binary_search_array", "binary_search_answer_space"}

    def detect(self, trace, intent, expectation, cfg) -> List[Divergence]:
        divergences: List[Divergence] = []
        loop = self._find_first(cfg, ast.While)
        loop_line = getattr(loop, "lineno", self._find_line_containing(cfg, "while", default=1))

        if isinstance(loop, ast.While) and self._uses_strict_bounds(loop.test):
            divergences.append(
                self._make_divergence(
                    divergence_type="PREMATURE_TERMINATION",
                    severity="HIGH",
                    line=loop_line,
                    expected_behavior=(
                        "Array binary search should keep the single-element search space alive "
                        "until that final candidate is checked."
                    ),
                    actual_behavior=(
                        "The loop uses `low < high`, so execution stops as soon as the search "
                        "space shrinks to one element and never checks that final candidate."
                    ),
                    algorithm_context=(
                        "Binary search correctness depends on preserving the invariant that the "
                        "answer remains inside the active bounds until every remaining candidate "
                        "has been tested or ruled out."
                    ),
                    fix_suggestion=f"On line {loop_line}, change the condition to `while low <= high:`.",
                    affected_variables=["low", "high"],
                    causal_chain=[
                        self._make_causal_step(
                            step_index=0,
                            description="The search loop terminates before the single-element case.",
                            lineno=loop_line,
                            why_this_matters=(
                                "A one-element interval is still a valid search space in array "
                                "binary search."
                            ),
                        )
                    ],
                )
            )

        stale_update = self._find_mid_stalling_update(cfg)
        if stale_update is not None:
            update_line = getattr(stale_update, "lineno", loop_line)
            target = self._ast_text(stale_update).strip()
            divergences.append(
                self._make_divergence(
                    divergence_type="LOOP_BOUND_ERROR",
                    severity="HIGH",
                    line=update_line,
                    expected_behavior=(
                        "Each binary-search iteration should exclude `mid` from one side of the "
                        "search interval with `mid + 1` or `mid - 1`."
                    ),
                    actual_behavior=(
                        f"The update `{target}` keeps `mid` inside the search space, so the "
                        "bounds may stop shrinking."
                    ),
                    algorithm_context=(
                        "Binary search only makes progress if every iteration strictly reduces the "
                        "candidate interval."
                    ),
                    fix_suggestion=(
                        "Advance the lower bound with `low = mid + 1` or reduce the upper bound "
                        "with `high = mid - 1`, depending on which half you eliminate."
                    ),
                    affected_variables=["low", "high", "mid"],
                )
            )

        return divergences

    def _uses_strict_bounds(self, test: ast.AST) -> bool:
        return (
            isinstance(test, ast.Compare)
            and len(test.ops) == 1
            and isinstance(test.left, ast.Name)
            and len(test.comparators) == 1
            and isinstance(test.comparators[0], ast.Name)
            and {test.left.id, test.comparators[0].id} == {"low", "high"}
            and isinstance(test.ops[0], ast.Lt)
        )

    def _find_mid_stalling_update(self, cfg) -> ast.AST | None:
        for node in self._iter_nodes(cfg, (ast.Assign, ast.AugAssign)):
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                target = node.targets[0].id
                value = node.value
                if target in {"low", "high"} and isinstance(value, ast.Name) and value.id == "mid":
                    return node
            if isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
                if node.target.id in {"low", "high"} and self._ast_text(node.value) == "mid":
                    return node
        return None
