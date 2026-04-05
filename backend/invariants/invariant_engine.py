from __future__ import annotations

import re
from typing import Any, Dict, List

from backend.api.models import InvariantObservation


class InvariantEngine:
    def analyze(self, trace, intent, expectation, parse_context, divergences) -> List[InvariantObservation]:
        reports: List[InvariantObservation] = []
        divergence_types = {item.type for item in divergences}
        divergence_steps = {
            step.step_index
            for divergence in divergences
            for step in divergence.causal_chain
            if hasattr(step, "step_index") and step.step_index
        }

        invariants = getattr(intent, "invariants", []) or []
        for invariant in invariants:
            expected = invariant.formal_expression or invariant.description
            observation = self._generic_observation(invariant.description, expected, trace, divergence_types, divergence_steps)
            reports.append(observation)

        reports.extend(self._algorithm_specific_reports(trace, intent, parse_context, divergences))
        return self._dedupe_reports(reports)

    def _generic_observation(self, description: str, expected: str, trace, divergence_types: set[str], divergence_steps: set[int]) -> InvariantObservation:
        violating = bool(divergence_types & {"INVARIANT_VIOLATION", "SEMANTIC_MISMATCH"})
        observed = (
            "A downstream divergence indicates that this invariant stopped holding during execution."
            if violating
            else "No deterministic evidence showed this invariant being broken in the captured trace."
        )
        return InvariantObservation(
            invariant=description,
            expected_condition=expected,
            observed_condition=observed,
            violation=violating,
            related_steps=sorted(divergence_steps),
            line_numbers=sorted({step.lineno for step in getattr(trace, 'steps', []) or [] if step.step_id in divergence_steps}),
            confidence=0.7 if violating else 0.55,
            evidence={"source": "intent_invariant"},
        )

    def _algorithm_specific_reports(self, trace, intent, parse_context, divergences) -> List[InvariantObservation]:
        algorithm = getattr(intent, "inferred_algorithm", "")
        reports: List[InvariantObservation] = []
        if algorithm == "sliding_window_fixed":
            reports.append(self._sliding_window_report(trace, intent, divergences))
        if algorithm.startswith("bfs"):
            reports.append(self._bfs_report(trace, divergences))
        if algorithm.startswith("dp"):
            reports.append(self._dp_report(trace, divergences))
        if algorithm.startswith("heap") or "heapq" in (parse_context.get("imports", []) if parse_context else []):
            reports.append(self._heap_report(trace, divergences))
        return [report for report in reports if report is not None]

    def _sliding_window_report(self, trace, intent, divergences) -> InvariantObservation:
        violated = any(item.type in {"WINDOW_INCOMPLETENESS", "WRONG_WINDOW_UPDATE", "OFF_BY_ONE"} for item in divergences)
        expected = "Window span should remain consistent with the intended fixed-size traversal."
        observed = (
            "The trace/divergence report shows a missing or malformed window update."
            if violated
            else "No divergence indicated a window-size mismatch."
        )
        return InvariantObservation(
            invariant="Sliding window size remains consistent across iterations.",
            expected_condition=expected,
            observed_condition=observed,
            violation=violated,
            confidence=0.78,
            evidence={"algorithm": intent.inferred_algorithm},
        )

    def _bfs_report(self, trace, divergences) -> InvariantObservation:
        violated = any(item.type in {"WRONG_VISITED_CHECK", "BFS_VISITED_LATE"} for item in divergences)
        observed = (
            "A visited-timing divergence shows nodes can be enqueued before they are marked visited."
            if violated
            else "No visited-timing divergence was detected."
        )
        return InvariantObservation(
            invariant="Visited nodes must not be re-enqueued.",
            expected_condition="Each node is marked visited before or at enqueue time.",
            observed_condition=observed,
            violation=violated,
            confidence=0.82,
            evidence={"algorithm": "bfs"},
        )

    def _heap_report(self, trace, divergences) -> InvariantObservation:
        violated = any(item.type in {"HEAP_INDEX_ERROR", "HEAP_PROPERTY_VIOLATION", "WRONG_HEAP_SIZE_MAINTENANCE"} for item in divergences)
        root_checks: List[str] = []
        for step in getattr(trace, "steps", []) or []:
            for name, value in (step.variable_snapshot or {}).items():
                if isinstance(value, list) and value:
                    smallest = min(value)
                    if value[0] != smallest:
                        root_checks.append(f"{name}[0]={value[0]!r} while min({name})={smallest!r}")
                        violated = True
                        break
            if root_checks:
                break
        observed = root_checks[0] if root_checks else (
            "No captured heap snapshot contradicted the root-order invariant."
        )
        return InvariantObservation(
            invariant="Heap root must satisfy the heap-order property.",
            expected_condition="For a min-heap, root equals the smallest available element.",
            observed_condition=observed,
            violation=violated,
            confidence=0.8,
            evidence={"algorithm": "heap"},
        )

    def _dp_report(self, trace, divergences) -> InvariantObservation:
        violated = any(item.type in {"DP_TRANSITION_ERROR", "DP_STATE_INCONSISTENCY"} for item in divergences)
        transition_issue = None
        for step in getattr(trace, "steps", []) or []:
            writes = list(getattr(step, "write_accesses", []) or [])
            reads = list(getattr(step, "read_accesses", []) or [])
            write_indices = [_access_index(item) for item in writes if item.startswith("dp[")]
            read_indices = [_access_index(item) for item in reads if item.startswith("dp[")]
            if write_indices and read_indices:
                target = write_indices[0]
                if any(source is not None and target is not None and source >= target for source in read_indices):
                    transition_issue = f"Step {step.step_id} writes dp[{target}] using non-prior state(s) {read_indices}."
                    violated = True
                    break
        observed = transition_issue or "No transition in the trace obviously depended on an invalid future DP state."
        return InvariantObservation(
            invariant="DP states depend only on valid earlier states.",
            expected_condition="dp[i] should be computed from already-solved predecessor states only.",
            observed_condition=observed,
            violation=violated,
            confidence=0.77,
            evidence={"algorithm": "dp"},
        )

    def _dedupe_reports(self, reports: List[InvariantObservation]) -> List[InvariantObservation]:
        deduped: Dict[str, InvariantObservation] = {}
        for report in reports:
            existing = deduped.get(report.invariant)
            if existing is None or (report.violation and not existing.violation):
                deduped[report.invariant] = report
        return list(deduped.values())


def _access_index(access: str) -> int | None:
    match = re.match(r"[A-Za-z_][A-Za-z0-9_]*\[(\d+)\]", access)
    if not match:
        return None
    return int(match.group(1))
