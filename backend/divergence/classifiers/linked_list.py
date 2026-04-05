from __future__ import annotations

import uuid
from typing import List

from backend.api.models import Divergence
from backend.divergence.classifiers.base_classifier import BaseClassifier


class LinkedListClassifier(BaseClassifier):
    def applicable(self, intent) -> bool:
        return intent.inferred_algorithm == "linked_list"

    def detect(self, trace, intent, expectation, cfg) -> List[Divergence]:
        divergences: List[Divergence] = []
        source = cfg.get("source", "") if cfg else ""
        line = 1

        if "next" in source and "None" not in source and "null" not in source:
            divergences.append(
                Divergence(
                    divergence_id=str(uuid.uuid4()),
                    type="MISSING_NULL_CHECK",
                    severity="HIGH",
                    causal_chain=[],
                    first_occurrence_line=line,
                    symptom_line=line,
                    expected_behavior="Linked list traversal should guard against None.",
                    actual_behavior="No null check found before accessing next.",
                    affected_variables=["next"],
                    affected_lines=[line],
                    algorithm_context="Missing null checks can cause exceptions.",
                    fix_suggestion="Check for None before accessing node.next.",
                )
            )

        return divergences
