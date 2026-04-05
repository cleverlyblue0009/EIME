from __future__ import annotations

import uuid
from typing import List

from backend.api.models import Divergence
from backend.divergence.classifiers.base_classifier import BaseClassifier


class TrieClassifier(BaseClassifier):
    def applicable(self, intent) -> bool:
        return intent.inferred_algorithm == "trie_insert_search"

    def detect(self, trace, intent, expectation, cfg) -> List[Divergence]:
        divergences: List[Divergence] = []
        source = cfg.get("source", "") if cfg else ""
        line = 1

        if "is_end" in source and "is_end = True" not in source and "is_end=True" not in source:
            divergences.append(
                Divergence(
                    divergence_id=str(uuid.uuid4()),
                    type="TRIE_TERMINATION_ERROR",
                    severity="HIGH",
                    causal_chain=[],
                    first_occurrence_line=line,
                    symptom_line=line,
                    expected_behavior="Insert should mark word termination.",
                    actual_behavior="is_end flag never set to True.",
                    affected_variables=["is_end"],
                    affected_lines=[line],
                    algorithm_context="Without termination flags, search cannot distinguish prefixes.",
                    fix_suggestion="Set node.is_end = True after inserting last character.",
                )
            )

        return divergences
