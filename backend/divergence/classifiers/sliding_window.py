from __future__ import annotations

import ast
from typing import List

from backend.api.models import Divergence
from backend.divergence.classifiers.base_classifier import BaseClassifier


class SlidingWindowClassifier(BaseClassifier):
    def applicable(self, intent) -> bool:
        return intent.inferred_algorithm in {"sliding_window_fixed", "sliding_window_variable"}

    def detect(self, trace, intent, expectation, cfg) -> List[Divergence]:
        divergences: List[Divergence] = []

        if intent.inferred_algorithm == "sliding_window_fixed":
            divergences.extend(self._detect_fixed_window(trace, expectation, cfg))

        return divergences

    def _detect_fixed_window(self, trace, expectation, cfg) -> List[Divergence]:
        divergences: List[Divergence] = []
        source = self._source(cfg)
        tree = self._tree(cfg)
        if tree is None:
            return divergences

        loop_node = self._find_fixed_window_loop(cfg)
        loop_line = getattr(loop_node, "lineno", self._first_loop_line(cfg))

        if loop_node is not None and self._loop_bound_skips_last_window(loop_node):
            formula = "len(arr) - k + 1"
            if expectation and expectation.expected_loop_count_formulas.get("main_loop"):
                formula = expectation.expected_loop_count_formulas["main_loop"]

            divergences.append(
                self._make_divergence(
                    divergence_type="WINDOW_INCOMPLETENESS",
                    severity="CRITICAL",
                    line=loop_line,
                    expected_behavior=(
                        f"Fixed sliding window should iterate {formula} times so every "
                        "contiguous window, including the final one, is processed."
                    ),
                    actual_behavior=(
                        "The loop bound stops at len(arr) - k, so the final window "
                        "starting at index len(arr) - k is never evaluated."
                    ),
                    algorithm_context=(
                        "The core invariant of fixed-size sliding window is completeness: "
                        "every valid window position must be visited exactly once."
                    ),
                    fix_suggestion=(
                        f"On line {loop_line}, change the loop bound to "
                        "`range(len(arr) - k + 1)`."
                    ),
                    affected_variables=["i", "k"],
                    causal_chain=[
                        self._make_causal_step(
                            step_index=0,
                            description="Loop header excludes the last valid window start.",
                            lineno=loop_line,
                            why_this_matters=(
                                "A fixed-size window traversal is only correct if it reaches "
                                "the window ending at the final element."
                            ),
                        )
                    ],
                )
            )

        if loop_node is not None and self._recomputes_window_sum(loop_node):
            divergences.append(
                self._make_divergence(
                    divergence_type="WRONG_WINDOW_UPDATE",
                    severity="MEDIUM",
                    line=loop_line,
                    expected_behavior=(
                        "A fixed window should slide in O(1) per step by adding the entering "
                        "element and subtracting the leaving element."
                    ),
                    actual_behavior=(
                        "The window sum is recomputed from scratch inside the loop, which turns "
                        "an O(n) sliding-window pass into O(n*k)."
                    ),
                    algorithm_context=(
                        "Sliding-window performance depends on preserving the running aggregate "
                        "instead of rebuilding it each iteration."
                    ),
                    fix_suggestion=(
                        "Initialize the first window once, then update it with a single add/subtract "
                        "operation on each iteration."
                    ),
                    affected_variables=["window_sum"],
                )
            )

        if loop_node is not None and self._uses_window_sum(source) and not self._has_initial_window_setup(cfg, loop_line):
            divergences.append(
                self._make_divergence(
                    divergence_type="MISSING_INITIAL_WINDOW",
                    severity="HIGH",
                    line=loop_line,
                    expected_behavior=(
                        "Before the sliding loop begins, the first window should already be "
                        "materialized so later iterations only shift it forward."
                    ),
                    actual_behavior=(
                        "The code enters the main sliding loop without a clear first-window "
                        "initialization step."
                    ),
                    algorithm_context=(
                        "Fixed-size sliding window has a distinct initialization phase that seeds "
                        "the running state for all later shifts."
                    ),
                    fix_suggestion=(
                        "Compute the initial window sum before the loop, for example "
                        "`window_sum = sum(arr[:k])`."
                    ),
                    affected_variables=["window_sum", "k"],
                )
            )

        if loop_node is not None and not self._updates_result_in_loop(loop_node):
            result_line = self._find_line_containing(cfg, "max(", default=loop_line)
            divergences.append(
                self._make_divergence(
                    divergence_type="RESULT_NOT_UPDATED_IN_LOOP",
                    severity="HIGH",
                    line=result_line,
                    expected_behavior=(
                        "Each window position should immediately contribute to the running answer "
                        "once the window state is valid."
                    ),
                    actual_behavior=(
                        "The loop advances the window but does not update the result candidate "
                        "inside the loop body."
                    ),
                    algorithm_context=(
                        "Sliding window separates state maintenance from result extraction, but the "
                        "result still must be refreshed at every valid window position."
                    ),
                    fix_suggestion=(
                        "Update the answer inside the loop, for example "
                        "`max_sum = max(max_sum, window_sum)`."
                    ),
                    affected_variables=["result", "max_sum", "ans"],
                )
            )

        if trace and getattr(trace, "loop_summaries", None):
            for loop in trace.loop_summaries:
                if loop.header_line != loop_line:
                    continue
                if self._window_size_breaks_in_trace(loop):
                    divergences.append(
                        self._make_divergence(
                            divergence_type="INVARIANT_VIOLATION",
                            severity="CRITICAL",
                            line=loop_line,
                            expected_behavior="Window size should remain constant throughout the sliding phase.",
                            actual_behavior=(
                                "Trace snapshots show the inferred window boundaries stop preserving "
                                "a constant width during execution."
                            ),
                            algorithm_context=(
                                "If the window size drifts, later result updates no longer correspond "
                                "to the intended fixed-size subarray."
                            ),
                            fix_suggestion=(
                                "Keep the distance between the left and right window boundaries constant "
                                "throughout the loop."
                            ),
                        )
                    )
                    break

        return divergences

    def _find_fixed_window_loop(self, cfg) -> ast.For | None:
        for node in self._iter_nodes(cfg, ast.For):
            if isinstance(node.iter, ast.Call) and isinstance(node.iter.func, ast.Name) and node.iter.func.id == "range":
                if "len(" in self._ast_text(node.iter):
                    return node
        return None

    def _loop_bound_skips_last_window(self, loop_node: ast.For) -> bool:
        range_args = loop_node.iter.args if isinstance(loop_node.iter, ast.Call) else []
        if not range_args:
            return False
        upper = range_args[-1]
        return self._looks_like_len_minus_k(upper)

    def _looks_like_len_minus_k(self, node: ast.AST) -> bool:
        return (
            isinstance(node, ast.BinOp)
            and isinstance(node.op, ast.Sub)
            and isinstance(node.left, ast.Call)
            and isinstance(node.left.func, ast.Name)
            and node.left.func.id == "len"
            and not isinstance(node.right, ast.Constant)
        )

    def _recomputes_window_sum(self, loop_node: ast.For) -> bool:
        for node in ast.walk(loop_node):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "sum":
                return True
        return False

    def _uses_window_sum(self, source: str) -> bool:
        return "window_sum" in source or "curr_sum" in source or "current_sum" in source

    def _has_initial_window_setup(self, cfg, loop_line: int) -> bool:
        for node in self._iter_nodes(cfg, (ast.Assign, ast.AnnAssign)):
            if getattr(node, "lineno", loop_line + 1) >= loop_line:
                continue
            text = self._ast_text(node)
            if "sum(" in text or "[:k]" in text or "[:window_size]" in text:
                return True
        return False

    def _updates_result_in_loop(self, loop_node: ast.For) -> bool:
        for node in ast.walk(loop_node):
            if isinstance(node, ast.Assign):
                target_names = [target.id for target in node.targets if isinstance(target, ast.Name)]
                if any(name in {"result", "res", "ans", "best", "max_sum"} for name in target_names):
                    return True
            if isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
                if node.target.id in {"result", "res", "ans", "best", "max_sum"}:
                    return True
        return False

    def _window_size_breaks_in_trace(self, loop_summary) -> bool:
        snapshots = getattr(loop_summary, "per_iteration_snapshots", []) or []
        if not snapshots:
            return False

        key_pairs = [
            ("left", "right"),
            ("l", "r"),
            ("start", "end"),
        ]
        partner_key = None
        for left_key, right_key in key_pairs:
            if all(left_key in snap and right_key in snap for snap in snapshots):
                partner_key = (left_key, right_key)
                break

        if partner_key is None:
            return False

        left_key, right_key = partner_key
        widths = []
        for snap in snapshots:
            left = snap.get(left_key)
            right = snap.get(right_key)
            if not isinstance(left, int) or not isinstance(right, int):
                return False
            widths.append(right - left)

        return len(set(widths)) > 1
