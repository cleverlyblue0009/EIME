from __future__ import annotations

import ast
from typing import List

from backend.api.models import Divergence
from backend.divergence.classifiers.base_classifier import BaseClassifier


class GraphShortestPathClassifier(BaseClassifier):
    def applicable(self, intent) -> bool:
        return intent.inferred_algorithm in {"dijkstra", "graph_shortest_path"}

    def detect(self, trace, intent, expectation, cfg) -> List[Divergence]:
        divergences: List[Divergence] = []
        source = self._source(cfg)

        relax_line = self._find_relaxation_without_guard(cfg)
        if relax_line is not None:
            divergences.append(
                self._make_divergence(
                    divergence_type="WRONG_RELAXATION",
                    severity="HIGH",
                    line=relax_line,
                    expected_behavior="Shortest-path relaxation should only update a neighbor when the new path is strictly shorter.",
                    actual_behavior="The distance map is updated without a preceding comparison against the existing best distance.",
                    algorithm_context=(
                        "Shortest-path algorithms preserve a monotone improvement invariant. Unconditional "
                        "writes can overwrite a correct shorter path with a worse one."
                    ),
                    fix_suggestion="Guard each relaxation with a comparison such as `if dist[u] + w < dist[v]:`.",
                    affected_variables=["dist"],
                )
            )

        if ("heapq" in source or "heappush" in source) and not self._has_stale_entry_check(source):
            line = self._find_line_containing(cfg, "heappop", default=self._find_line_containing(cfg, "heapq", default=1))
            divergences.append(
                self._make_divergence(
                    divergence_type="MISSING_DECREASE_KEY",
                    severity="MEDIUM",
                    line=line,
                    expected_behavior="Heap-based Dijkstra should skip stale entries after pop.",
                    actual_behavior="The heap is used lazily, but popped entries are processed without checking whether their distance is outdated.",
                    algorithm_context=(
                        "Python `heapq` does not support decrease-key, so Dijkstra relies on lazy deletion "
                        "and a stale-entry guard to preserve correctness."
                    ),
                    fix_suggestion="After popping `(d, node)`, add a guard like `if d > dist[node]: continue`.",
                    affected_variables=["heap", "dist"],
                )
            )

        return divergences

    def _find_relaxation_without_guard(self, cfg) -> int | None:
        for node in self._iter_nodes(cfg, ast.Assign):
            if not isinstance(node, ast.Assign) or len(node.targets) != 1:
                continue
            target_text = self._ast_text(node.targets[0])
            if "dist[" not in target_text:
                continue
            if "dist" not in self._ast_text(node.value):
                continue
            parent_if = self._enclosing_compare(cfg, node)
            if parent_if is None or "dist" not in self._ast_text(parent_if.test):
                return getattr(node, "lineno", 1)
        return None

    def _enclosing_compare(self, cfg, target_node: ast.AST) -> ast.If | None:
        tree = self._tree(cfg)
        if tree is None:
            return None
        for node in ast.walk(tree):
            if not isinstance(node, ast.If):
                continue
            if any(child is target_node for child in ast.walk(node)):
                return node
        return None

    def _has_stale_entry_check(self, source: str) -> bool:
        return any(token in source for token in {"if d > dist", "if d != dist", "if current_dist > dist", "visited"})
