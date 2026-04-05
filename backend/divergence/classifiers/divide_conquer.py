from __future__ import annotations

import uuid
from typing import List

from backend.api.models import Divergence
from backend.divergence.classifiers.base_classifier import BaseClassifier


class DivideConquerClassifier(BaseClassifier):
    def applicable(self, intent) -> bool:
        return intent.inferred_algorithm == "divide_conquer"

    def detect(self, trace, intent, expectation, cfg) -> List[Divergence]:
        divergences: List[Divergence] = []
        source = cfg.get("source", "") if cfg else ""
        line = 1

        if "return" in source and "left" in source and "right" in source and "merge" not in source:
            divergences.append(
                Divergence(
                    divergence_id=str(uuid.uuid4()),
                    type="WRONG_MERGE_CONDITION",
                    severity="MEDIUM",
                    causal_chain=[],
                    first_occurrence_line=line,
                    symptom_line=line,
                    expected_behavior="Divide-and-conquer should combine results from subproblems.",
                    actual_behavior="No merge/combine step detected.",
                    affected_variables=[],
                    affected_lines=[line],
                    algorithm_context="Combining subproblem solutions is required for correctness.",
                    fix_suggestion="Merge results from left and right subproblems.",
                )
            )

        return divergences
