from __future__ import annotations

import uuid
from typing import List

from backend.api.models import Divergence
from backend.divergence.classifiers.base_classifier import BaseClassifier


class SegmentTreeClassifier(BaseClassifier):
    def applicable(self, intent) -> bool:
        return intent.inferred_algorithm == "segment_tree"

    def detect(self, trace, intent, expectation, cfg) -> List[Divergence]:
        divergences: List[Divergence] = []
        source = cfg.get("source", "") if cfg else ""
        line = 1

        if "segment" in source and "update" in source and "lazy" not in source:
            divergences.append(
                Divergence(
                    divergence_id=str(uuid.uuid4()),
                    type="MISSING_STATE_UPDATE",
                    severity="MEDIUM",
                    causal_chain=[],
                    first_occurrence_line=line,
                    symptom_line=line,
                    expected_behavior="Lazy propagation should be used for range updates.",
                    actual_behavior="No lazy propagation detected.",
                    affected_variables=[],
                    affected_lines=[line],
                    algorithm_context="Range updates without lazy propagation can be incorrect or slow.",
                    fix_suggestion="Implement lazy push-down in update/query.",
                )
            )

        return divergences
