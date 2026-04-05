from __future__ import annotations

import ast
from typing import List

from backend.api.models import Divergence
from backend.divergence.classifiers.base_classifier import BaseClassifier


class BacktrackingClassifier(BaseClassifier):
    def applicable(self, intent) -> bool:
        return intent.inferred_algorithm == "backtracking"

    def detect(self, trace, intent, expectation, cfg) -> List[Divergence]:
        divergences: List[Divergence] = []
        tree = self._tree(cfg)
        if tree is None:
            return divergences

        append_ref = self._find_result_append_reference(cfg)
        if append_ref is not None:
            line = getattr(append_ref, "lineno", 1)
            divergences.append(
                self._make_divergence(
                    divergence_type="RESULT_APPENDS_REFERENCE",
                    severity="HIGH",
                    line=line,
                    expected_behavior=(
                        "Backtracking should append a snapshot of the current path so each solution "
                        "remains frozen after recursion continues."
                    ),
                    actual_behavior=(
                        "The code appends the mutable `path` list itself, so all recorded solutions "
                        "can later change together as recursion mutates that same object."
                    ),
                    algorithm_context=(
                        "Backtracking solutions represent states in time. Appending the live list "
                        "breaks that invariant because Python stores the same list reference."
                    ),
                    fix_suggestion=(
                        f"On line {line}, append a copy instead: `result.append(path[:])`."
                    ),
                    affected_variables=["path", "result"],
                    causal_chain=[
                        self._make_causal_step(
                            step_index=0,
                            description="A mutable path list is stored by reference.",
                            lineno=line,
                            why_this_matters=(
                                "Later `append` and `pop` operations mutate the same list object "
                                "that previous solutions point to."
                            ),
                        )
                    ],
                )
            )

        missing_restore = self._find_missing_restore(cfg)
        if missing_restore is not None:
            line = getattr(missing_restore, "lineno", 1)
            divergences.append(
                self._make_divergence(
                    divergence_type="BACKTRACK_RESTORE_MISSING",
                    severity="CRITICAL",
                    line=line,
                    expected_behavior=(
                        "After each recursive branch returns, the local choice should be undone so "
                        "the next branch starts from the pre-call state."
                    ),
                    actual_behavior=(
                        "The recursive branch adds state before recursion but does not restore it "
                        "after the call."
                    ),
                    algorithm_context=(
                        "Backtracking depends on exact state restoration; otherwise choices leak "
                        "across sibling branches and corrupt the search tree."
                    ),
                    fix_suggestion=(
                        "Add the matching restore step after recursion, such as `path.pop()` or "
                        "`used.remove(choice)`."
                    ),
                    affected_variables=["path"],
                )
            )

        return divergences

    def _find_result_append_reference(self, cfg) -> ast.Call | None:
        for node in self._iter_nodes(cfg, ast.Call):
            if not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr != "append" or len(node.args) != 1:
                continue
            target = self._ast_text(node.func.value)
            arg = node.args[0]
            if target in {"result", "results", "ans", "output"} and isinstance(arg, ast.Name):
                if arg.id in {"path", "current_path", "subset", "perm"}:
                    return node
        return None

    def _find_missing_restore(self, cfg) -> ast.For | ast.While | None:
        for loop in self._iter_nodes(cfg, (ast.For, ast.While)):
            if not isinstance(loop, (ast.For, ast.While)):
                continue

            saw_state_add = False
            saw_recursive_call = False
            saw_restore = False

            for stmt in loop.body:
                text = self._ast_text(stmt)
                if ".append(" in text or ".add(" in text:
                    saw_state_add = True
                if saw_state_add and self._contains_recursive_name(stmt, cfg):
                    saw_recursive_call = True
                if saw_recursive_call and (".pop(" in text or ".remove(" in text):
                    saw_restore = True
                    break

            if saw_state_add and saw_recursive_call and not saw_restore:
                return loop

        return None

    def _contains_recursive_name(self, node: ast.AST, cfg) -> bool:
        function_names = {
            func.name
            for func in self._iter_nodes(cfg, ast.FunctionDef)
            if isinstance(func, ast.FunctionDef)
        }
        for call in ast.walk(node):
            if isinstance(call, ast.Call) and isinstance(call.func, ast.Name):
                if call.func.id in function_names:
                    return True
        return False
