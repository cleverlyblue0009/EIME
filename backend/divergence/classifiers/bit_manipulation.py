from __future__ import annotations

import uuid
from typing import List

from backend.api.models import Divergence
from backend.divergence.classifiers.base_classifier import BaseClassifier


class BitManipulationClassifier(BaseClassifier):
    def applicable(self, intent) -> bool:
        return intent.inferred_algorithm == "bit_manipulation"

    def detect(self, trace, intent, expectation, cfg) -> List[Divergence]:
        divergences: List[Divergence] = []
        source = cfg.get("source", "") if cfg else ""
        line = 1

        if "<<" in source and "1 <<" not in source:
            divergences.append(
                Divergence(
                    divergence_id=str(uuid.uuid4()),
                    type="WRONG_BIT_OPERATION",
                    severity="LOW",
                    causal_chain=[],
                    first_occurrence_line=line,
                    symptom_line=line,
                    expected_behavior="Bit shifts should use explicit bit masks where appropriate.",
                    actual_behavior="Shift operations detected without explicit masks.",
                    affected_variables=[],
                    affected_lines=[line],
                    algorithm_context="Incorrect shifts can misplace bits.",
                    fix_suggestion="Use explicit masks like (1 << k) when shifting.",
                )
            )

        return divergences
