from __future__ import annotations

import uuid
from typing import List

from backend.api.models import Divergence
from backend.divergence.classifiers.base_classifier import BaseClassifier


class TwoPointerClassifier(BaseClassifier):
    def applicable(self, intent) -> bool:
        return intent.inferred_algorithm.startswith("two_pointer")

    def detect(self, trace, intent, expectation, cfg) -> List[Divergence]:
        divergences: List[Divergence] = []
        source = cfg.get("source", "") if cfg else ""
        line = 1

        if "left <= right" in source:
            divergences.append(
                Divergence(
                    divergence_id=str(uuid.uuid4()),
                    type="OFF_BY_ONE",
                    severity="MEDIUM",
                    causal_chain=[],
                    first_occurrence_line=line,
                    symptom_line=line,
                    expected_behavior="Pointers should stop when they cross for opposite-end scans.",
                    actual_behavior="Loop uses <=, potentially processing center twice.",
                    affected_variables=["left", "right"],
                    affected_lines=[line],
                    algorithm_context="Two-pointer invariant expects left < right for opposite ends.",
                    fix_suggestion="Use left < right for opposite-end pointer loops.",
                )
            )

        if "left" in source and "right" in source:
            if "+=" not in source and "-=" not in source:
                divergences.append(
                    Divergence(
                        divergence_id=str(uuid.uuid4()),
                        type="WRONG_POINTER_ADVANCE",
                        severity="HIGH",
                        causal_chain=[],
                        first_occurrence_line=line,
                        symptom_line=line,
                        expected_behavior="At least one pointer must advance each iteration.",
                        actual_behavior="Pointers do not advance; loop can stall.",
                        affected_variables=["left", "right"],
                        affected_lines=[line],
                        algorithm_context="Two-pointer loops must make progress to terminate.",
                        fix_suggestion="Advance left/right appropriately inside the loop.",
                    )
                )

        return divergences
