from __future__ import annotations

import uuid
from typing import List

from backend.api.models import Divergence
from backend.divergence.classifiers.base_classifier import BaseClassifier


class GraphTopoClassifier(BaseClassifier):
    def applicable(self, intent) -> bool:
        return intent.inferred_algorithm == "topological_sort_kahn"

    def detect(self, trace, intent, expectation, cfg) -> List[Divergence]:
        divergences: List[Divergence] = []
        source = cfg.get("source", "") if cfg else ""
        line = 1

        if "in_degree" in source and "len(result)" not in source and "cycle" not in source:
            divergences.append(
                Divergence(
                    divergence_id=str(uuid.uuid4()),
                    type="MISSING_EDGE_CASE",
                    severity="MEDIUM",
                    causal_chain=[],
                    first_occurrence_line=line,
                    symptom_line=line,
                    expected_behavior="Topological sort should detect cycles when nodes remain.",
                    actual_behavior="No cycle detection based on result length.",
                    affected_variables=["in_degree"],
                    affected_lines=[line],
                    algorithm_context="Without cycle checks, invalid orders may be reported.",
                    fix_suggestion="Check if len(result) < n to detect cycles.",
                )
            )

        return divergences
