from __future__ import annotations

import ast
from typing import List

from backend.api.models import Divergence
from backend.divergence.classifiers.base_classifier import BaseClassifier


class BFSClassifier(BaseClassifier):
    def applicable(self, intent) -> bool:
        return intent.inferred_algorithm.startswith("bfs")

    def detect(self, trace, intent, expectation, cfg) -> List[Divergence]:
        divergences: List[Divergence] = []

        visited_after_pop = self._find_visited_after_dequeue(cfg)
        if visited_after_pop is not None:
            line = getattr(visited_after_pop, "lineno", 1)
            divergences.append(
                self._make_divergence(
                    divergence_type="WRONG_VISITED_CHECK",
                    severity="HIGH",
                    line=line,
                    expected_behavior=(
                        "Standard BFS should mark a node visited at enqueue time so the queue never "
                        "contains duplicate copies of the same frontier node."
                    ),
                    actual_behavior=(
                        "The code marks `visited` after dequeue, so the same node can be enqueued "
                        "multiple times before its first pop."
                    ),
                    algorithm_context=(
                        "BFS shortest-path reasoning assumes the first enqueue reaches a node at "
                        "minimum depth. Delayed marking breaks that level invariant."
                    ),
                    fix_suggestion=(
                        "Move `visited.add(neighbor)` to the enqueue branch and seed the start node "
                        "as visited before the loop."
                    ),
                    affected_variables=["visited", "queue"],
                )
            )

        if self._missing_graph_edge_case(cfg):
            line = self._find_line_containing(cfg, "def ", default=1)
            divergences.append(
                self._make_divergence(
                    divergence_type="MISSING_EDGE_CASE",
                    severity="MEDIUM",
                    line=line,
                    expected_behavior="BFS should guard obvious edge cases like an empty graph or a missing start node.",
                    actual_behavior="No edge-case guard is present before graph access begins.",
                    algorithm_context=(
                        "Graph traversals should fail gracefully when the initial frontier cannot be formed."
                    ),
                    fix_suggestion=(
                        "Add a guard such as `if not graph or start not in graph: return -1` before "
                        "initializing the BFS loop."
                    ),
                    affected_variables=["graph", "start"],
                )
            )

        return divergences

    def _find_visited_after_dequeue(self, cfg) -> ast.Call | None:
        for loop in self._iter_nodes(cfg, ast.While):
            if not isinstance(loop, ast.While):
                continue
            saw_pop = False
            for stmt in loop.body:
                text = self._ast_text(stmt)
                if ".popleft(" in text or ".pop(0)" in text:
                    saw_pop = True
                if saw_pop and "visited.add(" in text:
                    return stmt if isinstance(stmt, ast.Call) else self._find_first_in_stmt(stmt, "visited.add")
        return None

    def _find_first_in_stmt(self, stmt: ast.stmt, needle: str) -> ast.Call | None:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Call) and needle in self._ast_text(node):
                return node
        return None

    def _missing_graph_edge_case(self, cfg) -> bool:
        source = self._source(cfg)
        mentions_graph = "graph[" in source or "graph." in source
        has_guard = "if not graph" in source or "start not in graph" in source or "if start not in graph" in source
        return mentions_graph and not has_guard
