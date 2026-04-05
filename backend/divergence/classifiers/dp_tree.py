from __future__ import annotations

import uuid
from typing import List

from backend.api.models import Divergence
from backend.divergence.classifiers.base_classifier import BaseClassifier


class DPTreeClassifier(BaseClassifier):
    def applicable(self, intent) -> bool:
        return intent.inferred_algorithm in {"dp_tree", "tree_dp"}

    def detect(self, trace, intent, expectation, cfg) -> List[Divergence]:
        divergences: List[Divergence] = []
        source = cfg.get("source", "") if cfg else ""
        line = 1

        if "left" in source and "right" in source and "return" in source:
            if "left + right" in source:
                divergences.append(
                    Divergence(
                        divergence_id=str(uuid.uuid4()),
                        type="DP_TRANSITION_ERROR",
                        severity="HIGH",
                        causal_chain=[],
                        first_occurrence_line=line,
                        symptom_line=line,
                        expected_behavior="Tree DP should return one-sided path values.",
                        actual_behavior="Function returns left + right (cross-path) directly.",
                        affected_variables=["left", "right"],
                        affected_lines=[line],
                        algorithm_context="Tree DP should return max(left, right) + 1 while updating global.",
                        fix_suggestion="Return max(left, right) + 1; update global with left+right.",
                    )
                )

        return divergences
