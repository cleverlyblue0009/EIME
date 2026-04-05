from __future__ import annotations

import ast
from typing import List

from backend.api.models import Divergence
from backend.divergence.classifiers.base_classifier import BaseClassifier


class UnionFindClassifier(BaseClassifier):
    def applicable(self, intent) -> bool:
        return intent.inferred_algorithm == "union_find"

    def detect(self, trace, intent, expectation, cfg) -> List[Divergence]:
        divergences: List[Divergence] = []
        source = self._source(cfg)

        union_func = self._named_function(cfg, "union")
        find_func = self._named_function(cfg, "find")

        if union_func is not None and "find(" not in self._ast_text(union_func):
            line = getattr(union_func, "lineno", 1)
            divergences.append(
                self._make_divergence(
                    divergence_type="WRONG_UNION_ORDER",
                    severity="HIGH",
                    line=line,
                    expected_behavior="Union should attach the roots returned by `find`, not the raw input nodes.",
                    actual_behavior="The `union` implementation links values without first normalizing them to their component roots.",
                    algorithm_context=(
                        "Union-Find correctness depends on operating at the representative level; "
                        "linking non-roots can corrupt the forest structure."
                    ),
                    fix_suggestion="Inside `union`, call `find(x)` and `find(y)` first, then link those roots.",
                    affected_variables=["parent"],
                )
            )

        if find_func is not None and "parent[" in self._ast_text(find_func) and "find(" in self._ast_text(find_func):
            if "parent[" in self._ast_text(find_func) and " = find(" not in self._ast_text(find_func):
                line = getattr(find_func, "lineno", 1)
                divergences.append(
                    self._make_divergence(
                        divergence_type="MISSING_STATE_UPDATE",
                        severity="LOW",
                        line=line,
                        expected_behavior="Path compression should rewrite intermediate parents directly to the root.",
                        actual_behavior="`find` performs recursive lookup without compressing the traversed path.",
                        algorithm_context=(
                            "Path compression is what gives Union-Find its near-constant amortized time."
                        ),
                        fix_suggestion="Assign the recursive root back into the parent array, for example `parent[x] = find(parent[x])`.",
                        affected_variables=["parent"],
                    )
                )

        if "union" in source and "rank" not in source and "size" not in source:
            line = getattr(union_func, "lineno", self._find_line_containing(cfg, "union", default=1))
            divergences.append(
                self._make_divergence(
                    divergence_type="WRONG_UNION_ORDER",
                    severity="LOW",
                    line=line,
                    expected_behavior="Union by rank or size should keep trees shallow.",
                    actual_behavior="The structure links components without any balancing heuristic.",
                    algorithm_context=(
                        "Even if correctness survives, unbalanced unions can degrade the intended performance."
                    ),
                    fix_suggestion="Track rank or size and always attach the smaller tree under the larger root.",
                    affected_variables=["parent", "rank", "size"],
                )
            )

        return divergences

    def _named_function(self, cfg, name: str) -> ast.FunctionDef | None:
        for node in self._iter_nodes(cfg, ast.FunctionDef):
            if isinstance(node, ast.FunctionDef) and node.name == name:
                return node
        return None
