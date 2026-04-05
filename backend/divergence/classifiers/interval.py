from __future__ import annotations

import uuid
from typing import List

from backend.api.models import Divergence
from backend.divergence.classifiers.base_classifier import BaseClassifier


class IntervalClassifier(BaseClassifier):
    def applicable(self, intent) -> bool:
        return intent.inferred_algorithm == "interval_merge"

    def detect(self, trace, intent, expectation, cfg) -> List[Divergence]:
        divergences: List[Divergence] = []
        source = cfg.get("source", "") if cfg else ""
        line = 1

        if "interval" in source and "<=" not in source and "<" in source:
            divergences.append(
                Divergence(
                    divergence_id=str(uuid.uuid4()),
                    type="WRONG_MERGE_CONDITION",
                    severity="MEDIUM",
                    causal_chain=[],
                    first_occurrence_line=line,
                    symptom_line=line,
                    expected_behavior="Intervals that touch should be merged with <= condition.",
                    actual_behavior="Merge condition uses strict < comparison.",
                    affected_variables=["intervals"],
                    affected_lines=[line],
                    algorithm_context="Strict comparison can miss touching intervals.",
                    fix_suggestion="Use <= when checking overlap for merging.",
                )
            )

        return divergences
