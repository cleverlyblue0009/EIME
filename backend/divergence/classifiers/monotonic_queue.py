from __future__ import annotations

import uuid
from typing import List

from backend.api.models import Divergence
from backend.divergence.classifiers.base_classifier import BaseClassifier


class MonotonicQueueClassifier(BaseClassifier):
    def applicable(self, intent) -> bool:
        return intent.inferred_algorithm == "monotonic_queue"

    def detect(self, trace, intent, expectation, cfg) -> List[Divergence]:
        divergences: List[Divergence] = []
        source = cfg.get("source", "") if cfg else ""
        line = 1

        if "deque" in source and "append" in source and "append(i" not in source:
            divergences.append(
                Divergence(
                    divergence_id=str(uuid.uuid4()),
                    type="MONOTONIC_VIOLATION",
                    severity="MEDIUM",
                    causal_chain=[],
                    first_occurrence_line=line,
                    symptom_line=line,
                    expected_behavior="Monotonic queue should store indices to manage window bounds.",
                    actual_behavior="Queue appears to store values directly.",
                    affected_variables=["deque"],
                    affected_lines=[line],
                    algorithm_context="Indices are needed to evict out-of-window elements.",
                    fix_suggestion="Store indices and compare values via the array.",
                )
            )

        return divergences
