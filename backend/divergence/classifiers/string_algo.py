from __future__ import annotations

import uuid
from typing import List

from backend.api.models import Divergence
from backend.divergence.classifiers.base_classifier import BaseClassifier


class StringAlgoClassifier(BaseClassifier):
    def applicable(self, intent) -> bool:
        return intent.inferred_algorithm == "string_algo"

    def detect(self, trace, intent, expectation, cfg) -> List[Divergence]:
        divergences: List[Divergence] = []
        source = cfg.get("source", "") if cfg else ""
        line = 1

        if "hash" in source and "mod" not in source and "%" not in source:
            divergences.append(
                Divergence(
                    divergence_id=str(uuid.uuid4()),
                    type="WRONG_HASH_FUNCTION",
                    severity="MEDIUM",
                    causal_chain=[],
                    first_occurrence_line=line,
                    symptom_line=line,
                    expected_behavior="Rolling hash should use a modulus to avoid overflow/collisions.",
                    actual_behavior="Hash computed without modulus.",
                    affected_variables=["hash"],
                    affected_lines=[line],
                    algorithm_context="Poor hashing increases collision risk.",
                    fix_suggestion="Apply modulus when updating rolling hash.",
                )
            )

        return divergences
