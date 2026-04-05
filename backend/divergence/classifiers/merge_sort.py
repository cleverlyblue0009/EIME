from __future__ import annotations

import uuid
from typing import List

from backend.api.models import Divergence
from backend.divergence.classifiers.base_classifier import BaseClassifier


class MergeSortClassifier(BaseClassifier):
    def applicable(self, intent) -> bool:
        return intent.inferred_algorithm == "merge_sort"

    def detect(self, trace, intent, expectation, cfg) -> List[Divergence]:
        divergences: List[Divergence] = []
        source = cfg.get("source", "") if cfg else ""
        line = 1

        if "mid" in source and "merge" not in source:
            divergences.append(
                Divergence(
                    divergence_id=str(uuid.uuid4()),
                    type="WRONG_MERGE_CONDITION",
                    severity="HIGH",
                    causal_chain=[],
                    first_occurrence_line=line,
                    symptom_line=line,
                    expected_behavior="Merge step should combine sorted halves.",
                    actual_behavior="No merge step detected.",
                    affected_variables=[],
                    affected_lines=[line],
                    algorithm_context="Merge sort correctness depends on merging sorted halves.",
                    fix_suggestion="Implement a merge step to combine left/right halves.",
                )
            )

        if "<" in source and "<=" not in source and "merge" in source:
            divergences.append(
                Divergence(
                    divergence_id=str(uuid.uuid4()),
                    type="WRONG_MERGE_CONDITION",
                    severity="LOW",
                    causal_chain=[],
                    first_occurrence_line=line,
                    symptom_line=line,
                    expected_behavior="Merge should use <= to preserve stability when needed.",
                    actual_behavior="Merge uses strict < comparison.",
                    affected_variables=[],
                    affected_lines=[line],
                    algorithm_context="Stability matters for some merge-sort-based solutions.",
                    fix_suggestion="Use <= in merge comparison where stability is required.",
                )
            )

        return divergences
