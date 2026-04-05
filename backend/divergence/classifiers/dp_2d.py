from __future__ import annotations

import uuid
from typing import List

from backend.api.models import Divergence
from backend.divergence.classifiers.base_classifier import BaseClassifier


class DP2DClassifier(BaseClassifier):
    def applicable(self, intent) -> bool:
        return intent.inferred_algorithm in {"dp_2d_grid", "dp_lcs", "dp_edit_distance"}

    def detect(self, trace, intent, expectation, cfg) -> List[Divergence]:
        divergences: List[Divergence] = []
        source = cfg.get("source", "") if cfg else ""
        line = 1

        if "dp" in source and "dp[0]" not in source and "dp[0][" not in source:
            divergences.append(
                Divergence(
                    divergence_id=str(uuid.uuid4()),
                    type="BASE_CASE_MISSING",
                    severity="MEDIUM",
                    causal_chain=[],
                    first_occurrence_line=line,
                    symptom_line=line,
                    expected_behavior="DP table boundaries should be initialized.",
                    actual_behavior="No base row/column initialization detected.",
                    affected_variables=["dp"],
                    affected_lines=[line],
                    algorithm_context="Boundary initialization prevents index errors and defines base cases.",
                    fix_suggestion="Initialize dp[0][*] and dp[*][0] before loops.",
                )
            )

        return divergences
