from __future__ import annotations

import uuid
from typing import List

from backend.api.models import Divergence
from backend.divergence.classifiers.base_classifier import BaseClassifier


class MonotonicStackClassifier(BaseClassifier):
    def applicable(self, intent) -> bool:
        return intent.inferred_algorithm == "monotonic_stack"

    def detect(self, trace, intent, expectation, cfg) -> List[Divergence]:
        divergences: List[Divergence] = []
        source = cfg.get("source", "") if cfg else ""
        line = 1

        if "stack.append" in source and "index" not in source:
            divergences.append(
                Divergence(
                    divergence_id=str(uuid.uuid4()),
                    type="WRONG_POINTER_ADVANCE",
                    severity="MEDIUM",
                    causal_chain=[],
                    first_occurrence_line=line,
                    symptom_line=line,
                    expected_behavior="Monotonic stack should store indices for distance computation.",
                    actual_behavior="Stack stores raw values; spans cannot be computed.",
                    affected_variables=["stack"],
                    affected_lines=[line],
                    algorithm_context="Index tracking is required for next-greater problems.",
                    fix_suggestion="Push indices onto the stack instead of values.",
                )
            )

        return divergences
