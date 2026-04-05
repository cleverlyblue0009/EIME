from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional

from backend.api.models import CausalStep, Divergence

_SEVERITY_ORDER = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}


class AdvancedPatternEngine:
    def detect(self, trace, intent, expectation, parse_context) -> List[Divergence]:
        divergences: List[Divergence] = []
        divergences.extend(self._detect_loop_boundary(trace, intent, expectation))
        divergences.extend(self._detect_sliding_window_invariant(trace, intent, expectation))
        divergences.extend(self._detect_bfs_trace_divergence(trace, intent))
        divergences.extend(self._detect_heap_index_error(trace, intent))
        divergences.extend(self._detect_heap_size_drift(trace, intent))
        divergences.extend(self._detect_dp_state_inconsistency(trace, intent, expectation))
        return divergences

    def _detect_loop_boundary(self, trace, intent, expectation) -> List[Divergence]:
        if not getattr(trace, "loop_summaries", None) or not expectation.expected_loop_counts:
            return []

        loop = trace.loop_summaries[0]
        expected_iterations = next(iter(expectation.expected_loop_counts.values()))
        actual_iterations = loop.iteration_count
        if not isinstance(expected_iterations, int) or expected_iterations == actual_iterations:
            return []

        missing = max(expected_iterations - actual_iterations, 0)
        if intent.inferred_algorithm == "sliding_window_fixed" and missing > 0:
            divergence_type = "WINDOW_INCOMPLETENESS"
            explanation = "The loop exits before the final valid fixed-size window is evaluated."
        elif missing == 1:
            divergence_type = "LOOP_MISSING_LAST_ITERATION"
            explanation = "The loop misses the final required iteration."
        else:
            divergence_type = "LOOP_BOUND_ERROR"
            explanation = "The observed loop count does not match the expected semantic iteration count."

        related_steps = self._steps_for_group(trace, f"loop:{loop.header_line}")
        causal_chain = self._causal_chain(
            related_steps[:1] + related_steps[-1:],
            "The loop boundary defines whether the algorithm reaches its final required state.",
        )

        return [
            Divergence(
                type=divergence_type,
                severity="CRITICAL" if missing > 0 else "MEDIUM",
                causal_chain=causal_chain,
                first_occurrence_line=loop.header_line,
                symptom_line=loop.header_line,
                expected_behavior="The main loop should visit every semantically required state exactly once.",
                actual_behavior=f"Observed {actual_iterations} iteration(s) instead of the expected {expected_iterations}.",
                affected_variables=[name for name in [loop.loop_variable] if name] or list(loop.variables_mutated[:3]),
                affected_lines=[loop.header_line],
                algorithm_context="Boundary mistakes are root-cause errors because they prevent later state transitions from happening at all.",
                fix_suggestion="Adjust the loop bound so the final valid case is included exactly once.",
                expected_state={
                    "expected_iterations": expected_iterations,
                    "loop_formula": next(iter(expectation.expected_loop_count_formulas.values()), None),
                },
                actual_state={"actual_iterations": actual_iterations},
                missing_state={"missing_iterations": missing} if missing > 0 else None,
                explanation=explanation,
                root_cause="Loop control stops before the semantic frontier is exhausted.",
                evidence={"loop_header_line": loop.header_line},
            )
        ]

    def _detect_sliding_window_invariant(self, trace, intent, expectation) -> List[Divergence]:
        if intent.inferred_algorithm != "sliding_window_fixed":
            return []

        for loop in getattr(trace, "loop_summaries", []) or []:
            snapshots = loop.per_iteration_snapshots or []
            pair = self._window_pair(snapshots)
            if pair is None:
                continue
            left_key, right_key = pair
            widths = []
            for snapshot in snapshots:
                left = snapshot.get(left_key)
                right = snapshot.get(right_key)
                if not isinstance(left, int) or not isinstance(right, int):
                    widths = []
                    break
                widths.append(right - left)
            if len(widths) >= 2 and len(set(widths)) > 1:
                bad_index = next(index for index, width in enumerate(widths) if width != widths[0])
                step = self._step_for_iteration(trace, loop.header_line, bad_index + 1)
                return [
                    Divergence(
                        type="INVARIANT_VIOLATION",
                        severity="CRITICAL",
                        causal_chain=self._causal_chain(
                            [item for item in [step] if item is not None],
                            "A fixed-size sliding window is only correct when its width stays constant.",
                        ),
                        first_occurrence_line=step.lineno if step else loop.header_line,
                        symptom_line=step.lineno if step else loop.header_line,
                        expected_behavior="The distance between the left and right boundary should remain constant.",
                        actual_behavior="The window width changes across iterations, so later states no longer represent the intended fixed-size window.",
                        affected_variables=[left_key, right_key],
                        affected_lines=[loop.header_line],
                        algorithm_context="When the window width drifts, the algorithm is no longer comparing equivalent candidate windows.",
                        fix_suggestion="Keep the boundary update symmetric so each shift removes one element and adds exactly one element.",
                        expected_state={"expected_width": widths[0]},
                        actual_state={"observed_widths": widths},
                        explanation="The execution trace shows that the sliding window loses its fixed-size invariant.",
                        root_cause="Boundary updates are no longer preserving a constant-width window.",
                        evidence={"loop_header_line": loop.header_line, "boundary_pair": [left_key, right_key]},
                    )
                ]
        return []

    def _detect_bfs_trace_divergence(self, trace, intent) -> List[Divergence]:
        if not intent.inferred_algorithm.startswith("bfs"):
            return []

        queue_key = self._pick_key(trace.final_state, {"queue", "q", "deque"})
        visited_key = self._pick_key(trace.final_state, {"visited", "seen", "used"})
        if not queue_key:
            return []

        for step in getattr(trace, "steps", []) or []:
            queue = step.variable_snapshot.get(queue_key)
            if not isinstance(queue, list) or len(queue) < 2:
                continue
            queue_signature = [repr(item) for item in queue]
            if len(queue_signature) == len(set(queue_signature)):
                continue
            visited = step.variable_snapshot.get(visited_key) if visited_key else None
            return [
                Divergence(
                    type="BFS_VISITED_LATE",
                    severity="HIGH",
                    causal_chain=self._causal_chain(
                        [step],
                        "Duplicate frontier entries mean the traversal marked nodes as visited too late.",
                    ),
                    first_occurrence_line=step.lineno,
                    symptom_line=step.lineno,
                    expected_behavior="A node should be marked visited before or at enqueue time so the frontier never contains duplicate copies.",
                    actual_behavior="The queue contains duplicate nodes before the visited state catches up.",
                    affected_variables=[name for name in [queue_key, visited_key] if name],
                    affected_lines=[step.lineno],
                    algorithm_context="BFS shortest-path and level-order semantics assume the first enqueue is the unique earliest discovery of a node.",
                    fix_suggestion="Move the visited update into the enqueue branch and seed the start node before the loop begins.",
                    expected_state={"frontier_rule": "queued nodes are already marked visited"},
                    actual_state={queue_key: queue, visited_key: visited} if visited_key else {queue_key: queue},
                    explanation="Execution shows duplicate frontier entries, which is the runtime symptom of a delayed visited update.",
                    root_cause="The traversal enqueues nodes before it commits them to the visited set.",
                    evidence={"queue_duplicates": True},
                )
            ]
        return []

    def _detect_heap_index_error(self, trace, intent) -> List[Divergence]:
        if "heap" not in intent.inferred_algorithm and "heap" not in (trace.final_state or {}):
            return []

        for step in getattr(trace, "steps", []) or []:
            bad_accesses = [
                access
                for access in step.read_accesses or []
                if access.startswith("heap[") and access not in {"heap[0]", "heap[-1]"}
            ]
            if not bad_accesses:
                continue
            heap_state = step.variable_snapshot.get("heap")
            return [
                Divergence(
                    type="HEAP_INDEX_ERROR",
                    severity="HIGH",
                    causal_chain=self._causal_chain(
                        [step],
                        "Heap logic should read the root when it needs the current best candidate.",
                    ),
                    first_occurrence_line=step.lineno,
                    symptom_line=step.lineno,
                    expected_behavior="Heap algorithms should read the active root from `heap[0]` unless they intentionally inspect a child.",
                    actual_behavior=f"The step reads {', '.join(bad_accesses)}, which suggests the algorithm is using a child slot as the heap top.",
                    affected_variables=["heap"],
                    affected_lines=[step.lineno],
                    algorithm_context="The heap root is the only position guaranteed to satisfy the global ordering invariant.",
                    fix_suggestion="Read the candidate from `heap[0]` or use `heappop()` when consuming the best element.",
                    expected_state={"top_index": 0},
                    actual_state={"heap": heap_state, "bad_accesses": bad_accesses},
                    explanation="The trace shows a child index being used where the algorithm likely expects the heap root.",
                    root_cause="The implementation is reading a structural child instead of the ordered root.",
                    evidence={"bad_accesses": bad_accesses},
                )
            ]
        return []

    def _detect_heap_size_drift(self, trace, intent) -> List[Divergence]:
        if "heap" not in intent.inferred_algorithm:
            return []

        k = trace.final_state.get("k") if hasattr(trace, "final_state") else None
        if not isinstance(k, int):
            return []

        for step in getattr(trace, "steps", []) or []:
            heap_state = step.variable_snapshot.get("heap")
            if isinstance(heap_state, list) and len(heap_state) > k:
                return [
                    Divergence(
                        type="WRONG_HEAP_SIZE_MAINTENANCE",
                        severity="MEDIUM",
                        causal_chain=self._causal_chain(
                            [step],
                            "Top-k style heap solutions must trim the heap immediately after an oversized push.",
                        ),
                        first_occurrence_line=step.lineno,
                        symptom_line=step.lineno,
                        expected_behavior="The heap size should stay bounded by k.",
                        actual_behavior=f"The heap grows to size {len(heap_state)} while k is {k}.",
                        affected_variables=["heap", "k"],
                        affected_lines=[step.lineno],
                        algorithm_context="When the heap grows beyond k, it stops representing the current best-k frontier.",
                        fix_suggestion="Pop the root after push whenever the heap size exceeds k.",
                        expected_state={"max_heap_size": k},
                        actual_state={"heap_size": len(heap_state), "heap": heap_state},
                        explanation="Runtime state shows the heap exceeding its intended capacity bound.",
                        root_cause="The code pushes new candidates without restoring the heap size invariant.",
                        evidence={"k": k},
                    )
                ]
        return []

    def _detect_dp_state_inconsistency(self, trace, intent, expectation) -> List[Divergence]:
        if not intent.inferred_algorithm.startswith("dp"):
            return []

        dp_key = self._pick_key(trace.final_state, {"dp", "memo", "cache"})
        expected_indices = expectation.expected_variable_final_values.get("expected_state_indices")
        if not dp_key or not isinstance(expected_indices, list):
            return []

        written_indices = sorted(
            {
                index
                for step in getattr(trace, "steps", []) or []
                for index in self._indices_from_accesses(step.write_accesses or [], dp_key)
            }
        )
        missing_indices = [index for index in expected_indices if index not in written_indices]
        if not missing_indices:
            return []

        last_relevant = next(
            (
                step
                for step in reversed(getattr(trace, "steps", []) or [])
                if dp_key in step.variable_snapshot or any(access.startswith(f"{dp_key}[") for access in step.write_accesses or [])
            ),
            None,
        )
        return [
            Divergence(
                type="DP_STATE_INCONSISTENCY",
                severity="HIGH",
                causal_chain=self._causal_chain(
                    [item for item in [last_relevant] if item is not None],
                    "DP correctness depends on visiting the full chain of required subproblems.",
                ),
                first_occurrence_line=last_relevant.lineno if last_relevant else 1,
                symptom_line=last_relevant.lineno if last_relevant else 1,
                expected_behavior="The DP table should materialize every required state before the final answer is read.",
                actual_behavior="The trace never writes one or more expected DP indices.",
                affected_variables=[dp_key],
                affected_lines=[last_relevant.lineno if last_relevant else 1],
                algorithm_context="If a DP state is missing, later transitions either reuse stale values or skip valid subproblems entirely.",
                fix_suggestion="Adjust the initialization or loop bounds so every required DP state is written before the return step.",
                expected_state={
                    "expected_indices": expected_indices,
                    "state_rule": expectation.expected_variable_final_values.get("state_progression_rule"),
                },
                actual_state={
                    "written_indices": written_indices,
                    dp_key: trace.final_state.get(dp_key),
                },
                missing_state={"missing_indices": missing_indices},
                explanation="The execution trace reveals holes in the DP state progression.",
                root_cause="One or more subproblems are skipped by the current transition schedule.",
                evidence={"dp_key": dp_key},
            )
        ]

    def _window_pair(self, snapshots: List[Dict[str, Any]]) -> Optional[tuple[str, str]]:
        for left_key, right_key in [("left", "right"), ("l", "r"), ("start", "end")]:
            if snapshots and all(left_key in snapshot and right_key in snapshot for snapshot in snapshots):
                return left_key, right_key
        return None

    def _steps_for_group(self, trace, group_id: str) -> List[Any]:
        return [step for step in getattr(trace, "steps", []) or [] if step.group_id == group_id]

    def _step_for_iteration(self, trace, header_line: int, iteration_index: int):
        for step in getattr(trace, "steps", []) or []:
            if step.group_id == f"loop:{header_line}" and step.iteration_index == iteration_index:
                return step
        return None

    def _pick_key(self, state: Dict[str, Any], candidates: set[str]) -> Optional[str]:
        for key in state.keys():
            if key in candidates:
                return key
        return None

    def _indices_from_accesses(self, accesses: Iterable[str], prefix: str) -> List[int]:
        indices: List[int] = []
        for access in accesses:
            if not access.startswith(f"{prefix}["):
                continue
            match = re.search(r"\[(\-?\d+)\]$", access)
            if not match:
                continue
            indices.append(int(match.group(1)))
        return indices

    def _causal_chain(self, steps: Iterable[Any], why: str) -> List[CausalStep]:
        chain: List[CausalStep] = []
        seen: set[int] = set()
        for step in steps:
            if step is None or step.step_id in seen:
                continue
            seen.add(step.step_id)
            chain.append(
                CausalStep(
                    step_index=step.step_id,
                    description=step.description,
                    lineno=step.lineno,
                    variable_state=step.variable_snapshot,
                    why_this_matters=why,
                )
            )
        return chain

    def richness(self, divergence: Divergence) -> tuple[int, int, int, int]:
        return (
            _SEVERITY_ORDER.get(divergence.severity, 0),
            1 if divergence.causal_chain else 0,
            1 if divergence.expected_state is not None else 0,
            1 if divergence.actual_state is not None else 0,
        )
