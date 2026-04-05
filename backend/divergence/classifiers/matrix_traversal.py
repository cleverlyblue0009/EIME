from __future__ import annotations

import ast
from typing import List

from backend.api.models import Divergence
from backend.divergence.classifiers.base_classifier import BaseClassifier


class MatrixTraversalClassifier(BaseClassifier):
    def applicable(self, intent) -> bool:
        return intent.inferred_algorithm == "matrix_traversal"

    def detect(self, trace, intent, expectation, cfg) -> List[Divergence]:
        divergences: List[Divergence] = []
        source = self._source(cfg)
        if not all(name in source for name in {"top", "bottom", "left", "right"}):
            return divergences

        if not self._updates_all_boundaries(cfg):
            line = self._find_line_containing(cfg, "top", default=1)
            divergences.append(
                self._make_divergence(
                    divergence_type="WRONG_DIRECTION",
                    severity="MEDIUM",
                    line=line,
                    expected_behavior="Spiral and boundary-based matrix traversals should shrink the active rectangle after each directional pass.",
                    actual_behavior="One or more boundary variables are never updated, so the traversal can revisit cells or fail to advance layers.",
                    algorithm_context=(
                        "Matrix traversal correctness comes from moving the active boundaries inward in lockstep with the traversal direction."
                    ),
                    fix_suggestion="Update `top`, `bottom`, `left`, and `right` after the corresponding directional sweeps.",
                    affected_variables=["top", "bottom", "left", "right"],
                )
            )

        return divergences

    def _updates_all_boundaries(self, cfg) -> bool:
        source = self._source(cfg)
        updates = {
            "top": any(token in source for token in {"top +=", "top = top +", "top = top + 1"}),
            "bottom": any(token in source for token in {"bottom -=", "bottom = bottom -", "bottom = bottom - 1"}),
            "left": any(token in source for token in {"left +=", "left = left +", "left = left + 1"}),
            "right": any(token in source for token in {"right -=", "right = right -", "right = right - 1"}),
        }
        return all(updates.values())
