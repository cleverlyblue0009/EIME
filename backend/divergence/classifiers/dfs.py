from __future__ import annotations

import uuid
from typing import List

from backend.api.models import Divergence
from backend.divergence.classifiers.base_classifier import BaseClassifier


class DFSClassifier(BaseClassifier):
    def applicable(self, intent) -> bool:
        return intent.inferred_algorithm.startswith("dfs")

    def detect(self, trace, intent, expectation, cfg) -> List[Divergence]:
        divergences: List[Divergence] = []
        source = cfg.get("source", "") if cfg else ""
        line = 1

        if "visited" in source and "dfs" in source:
            if "visited.add" in source and source.find("visited.add") > source.find("dfs"):
                divergences.append(
                    Divergence(
                        divergence_id=str(uuid.uuid4()),
                        type="WRONG_VISITED_CHECK",
                        severity="MEDIUM",
                        causal_chain=[],
                        first_occurrence_line=line,
                        symptom_line=line,
                        expected_behavior="Visited should be marked before recursive call.",
                        actual_behavior="Visited is marked after recursion.",
                        affected_variables=["visited"],
                        affected_lines=[line],
                        algorithm_context="DFS can revisit nodes without pre-visit marking.",
                        fix_suggestion="Mark visited before dfs(neighbor).",
                    )
                )

        if "append(" in source and "pop(" not in source:
            divergences.append(
                Divergence(
                    divergence_id=str(uuid.uuid4()),
                    type="BACKTRACK_RESTORE_MISSING",
                    severity="HIGH",
                    causal_chain=[],
                    first_occurrence_line=line,
                    symptom_line=line,
                    expected_behavior="Backtracking should restore state after recursion.",
                    actual_behavior="State restore step missing.",
                    affected_variables=[],
                    affected_lines=[line],
                    algorithm_context="Missing restore corrupts DFS path state.",
                    fix_suggestion="Add a corresponding pop/remove after recursion.",
                )
            )

        return divergences
