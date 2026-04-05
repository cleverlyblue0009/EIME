from __future__ import annotations

import uuid
from typing import List

from backend.api.models import Divergence
from backend.divergence.classifiers.base_classifier import BaseClassifier


class HeapClassifier(BaseClassifier):
    def applicable(self, intent) -> bool:
        return intent.inferred_algorithm.startswith("heap") or "heap" in intent.inferred_algorithm

    def detect(self, trace, intent, expectation, cfg) -> List[Divergence]:
        divergences: List[Divergence] = []
        source = cfg.get("source", "") if cfg else ""
        line = 1

        if "heap[0]" in source and "max" in source:
            divergences.append(
                Divergence(
                    divergence_id=str(uuid.uuid4()),
                    type="HEAP_PROPERTY_VIOLATION",
                    severity="MEDIUM",
                    causal_chain=[],
                    first_occurrence_line=line,
                    symptom_line=line,
                    expected_behavior="heap[0] is the minimum element in a min-heap.",
                    actual_behavior="Code treats heap[0] as maximum without negation.",
                    affected_variables=["heap"],
                    affected_lines=[line],
                    algorithm_context="Heap comparator must match intended order.",
                    fix_suggestion="Use negative values or a max-heap simulation.",
                )
            )

        if "heappush" in source and "heappop" not in source and "k" in source:
            divergences.append(
                Divergence(
                    divergence_id=str(uuid.uuid4()),
                    type="MISSING_STATE_UPDATE",
                    severity="MEDIUM",
                    causal_chain=[],
                    first_occurrence_line=line,
                    symptom_line=line,
                    expected_behavior="Heap should be trimmed to size k.",
                    actual_behavior="Heap grows without popping.",
                    affected_variables=["heap"],
                    affected_lines=[line],
                    algorithm_context="Top-k requires maintaining heap size.",
                    fix_suggestion="Pop when heap size exceeds k.",
                )
            )

        return divergences
