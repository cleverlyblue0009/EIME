from __future__ import annotations

import ast
from typing import List

from backend.api.models import Divergence
from backend.divergence.classifiers.base_classifier import BaseClassifier


class GraphMstClassifier(BaseClassifier):
    def applicable(self, intent) -> bool:
        return intent.inferred_algorithm in {"graph_mst", "graph_mst_kruskal", "graph_mst_prim"}

    def detect(self, trace, intent, expectation, cfg) -> List[Divergence]:
        divergences: List[Divergence] = []
        source = self._source(cfg)

        if "sorted" in source and "edge" in source and "union(" not in source and "visited" not in source:
            line = self._find_line_containing(cfg, "sorted", default=1)
            divergences.append(
                self._make_divergence(
                    divergence_type="WRONG_UNION_ORDER",
                    severity="HIGH",
                    line=line,
                    expected_behavior="Kruskal-style MST should union the endpoints of every accepted edge.",
                    actual_behavior="Edges are ordered, but the implementation never links components after selecting an edge.",
                    algorithm_context=(
                        "Minimum spanning tree selection only works when each accepted edge also updates "
                        "the component structure used to prevent cycles."
                    ),
                    fix_suggestion="Call `union(u, v)` immediately after accepting an edge into the MST.",
                    affected_variables=["edges", "parent"],
                )
            )

        sort_line = self._find_sort_without_key(cfg)
        if sort_line is not None and "weight" in source:
            divergences.append(
                self._make_divergence(
                    divergence_type="WRONG_SORT_KEY",
                    severity="MEDIUM",
                    line=sort_line,
                    expected_behavior="MST edge ordering should sort by edge weight explicitly.",
                    actual_behavior="Edges are sorted without a key function, so tuple layout or object ordering controls the choice.",
                    algorithm_context=(
                        "Kruskal's invariant is weight order. If the sort key is ambiguous, the MST "
                        "selection order is no longer guaranteed."
                    ),
                    fix_suggestion="Sort with `key=lambda edge: edge[2]` or the field that stores edge weight.",
                    affected_variables=["edges"],
                )
            )

        return divergences

    def _find_sort_without_key(self, cfg) -> int | None:
        for node in self._iter_nodes(cfg, ast.Call):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name) and node.func.id == "sorted":
                if not any(keyword.arg == "key" for keyword in node.keywords):
                    return getattr(node, "lineno", 1)
            if isinstance(node.func, ast.Attribute) and node.func.attr == "sort":
                if not any(keyword.arg == "key" for keyword in node.keywords):
                    return getattr(node, "lineno", 1)
        return None
