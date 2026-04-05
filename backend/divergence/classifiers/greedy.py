from __future__ import annotations

import uuid
from typing import List

from backend.api.models import Divergence
from backend.divergence.classifiers.base_classifier import BaseClassifier


class GreedyClassifier(BaseClassifier):
    def applicable(self, intent) -> bool:
        return intent.inferred_algorithm == "greedy"

    def detect(self, trace, intent, expectation, cfg) -> List[Divergence]:
        divergences: List[Divergence] = []
        source = cfg.get("source", "") if cfg else ""
        line = 1

        if "sorted" in source and "key" not in source:
            divergences.append(
                Divergence(
                    divergence_id=str(uuid.uuid4()),
                    type="WRONG_SORT_KEY",
                    severity="MEDIUM",
                    causal_chain=[],
                    first_occurrence_line=line,
                    symptom_line=line,
                    expected_behavior="Greedy algorithm should sort by the correct key.",
                    actual_behavior="Sorting occurs without an explicit key.",
                    affected_variables=[],
                    affected_lines=[line],
                    algorithm_context="Greedy choice depends on correct ordering.",
                    fix_suggestion="Sort with the problem-specific key (e.g., end time).")
            )

        return divergences
