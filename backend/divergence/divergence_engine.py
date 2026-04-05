from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Tuple

from backend.api.models import CausalStep, Divergence
from backend.divergence.advanced_engine import AdvancedPatternEngine
from backend.divergence.classifiers.backtracking import BacktrackingClassifier
from backend.divergence.classifiers.bfs import BFSClassifier
from backend.divergence.classifiers.binary_search import BinarySearchClassifier
from backend.divergence.classifiers.bit_manipulation import BitManipulationClassifier
from backend.divergence.classifiers.dfs import DFSClassifier
from backend.divergence.classifiers.divide_conquer import DivideConquerClassifier
from backend.divergence.classifiers.dp_1d import DP1DClassifier
from backend.divergence.classifiers.dp_2d import DP2DClassifier
from backend.divergence.classifiers.dp_tree import DPTreeClassifier
from backend.divergence.classifiers.general import GeneralClassifier
from backend.divergence.classifiers.graph_mst import GraphMstClassifier
from backend.divergence.classifiers.graph_shortest_path import GraphShortestPathClassifier
from backend.divergence.classifiers.graph_topo import GraphTopoClassifier
from backend.divergence.classifiers.greedy import GreedyClassifier
from backend.divergence.classifiers.heap import HeapClassifier
from backend.divergence.classifiers.interval import IntervalClassifier
from backend.divergence.classifiers.linked_list import LinkedListClassifier
from backend.divergence.classifiers.matrix_traversal import MatrixTraversalClassifier
from backend.divergence.classifiers.merge_sort import MergeSortClassifier
from backend.divergence.classifiers.monotonic_queue import MonotonicQueueClassifier
from backend.divergence.classifiers.monotonic_stack import MonotonicStackClassifier
from backend.divergence.classifiers.recursion_memo import RecursionMemoClassifier
from backend.divergence.classifiers.segment_tree import SegmentTreeClassifier
from backend.divergence.classifiers.sliding_window import SlidingWindowClassifier
from backend.divergence.classifiers.string_algo import StringAlgoClassifier
from backend.divergence.classifiers.trie import TrieClassifier
from backend.divergence.classifiers.two_pointer import TwoPointerClassifier
from backend.divergence.classifiers.union_find import UnionFindClassifier

_SEVERITY_ORDER = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}


class DivergenceEngine:
    def __init__(self) -> None:
        self.classifiers = [
            SlidingWindowClassifier(),
            BinarySearchClassifier(),
            TwoPointerClassifier(),
            MergeSortClassifier(),
            DP1DClassifier(),
            DP2DClassifier(),
            DPTreeClassifier(),
            BacktrackingClassifier(),
            GreedyClassifier(),
            TrieClassifier(),
            UnionFindClassifier(),
            SegmentTreeClassifier(),
            HeapClassifier(),
            MonotonicStackClassifier(),
            MonotonicQueueClassifier(),
            BFSClassifier(),
            DFSClassifier(),
            GraphShortestPathClassifier(),
            GraphTopoClassifier(),
            GraphMstClassifier(),
            RecursionMemoClassifier(),
            DivideConquerClassifier(),
            BitManipulationClassifier(),
            StringAlgoClassifier(),
            MatrixTraversalClassifier(),
            IntervalClassifier(),
            LinkedListClassifier(),
            GeneralClassifier(),
        ]
        self.advanced_patterns = AdvancedPatternEngine()

    def detect(self, trace, intent, expectation, parse_context) -> List[Divergence]:
        collected: List[Divergence] = []
        for classifier in self.classifiers:
            if classifier.applicable(intent):
                collected.extend(classifier.detect(trace, intent, expectation, parse_context))

        collected.extend(self.advanced_patterns.detect(trace, intent, expectation, parse_context))
        return self.finalize(collected, trace, intent, expectation)

    def finalize(self, divergences: List[Divergence], trace, intent, expectation) -> List[Divergence]:
        merged = self._dedupe_divergences(divergences)
        return [self._enrich_divergence(divergence, trace, intent, expectation) for divergence in merged]

    def _dedupe_divergences(self, divergences: List[Divergence]) -> List[Divergence]:
        merged: Dict[Tuple[str, int, int], Divergence] = {}
        for divergence in divergences:
            key = (divergence.type, divergence.first_occurrence_line, divergence.symptom_line)
            if key not in merged:
                merged[key] = divergence
                continue
            merged[key] = self._merge_divergence(merged[key], divergence)
        return sorted(
            merged.values(),
            key=lambda item: (_SEVERITY_ORDER.get(item.severity, 0), -item.first_occurrence_line),
            reverse=True,
        )

    def _merge_divergence(self, left: Divergence, right: Divergence) -> Divergence:
        preferred, candidate = (
            (deepcopy(left), right)
            if self._richness(left) >= self._richness(right)
            else (deepcopy(right), left)
        )

        if not preferred.causal_chain and candidate.causal_chain:
            preferred.causal_chain = candidate.causal_chain
        if preferred.expected_state is None and candidate.expected_state is not None:
            preferred.expected_state = candidate.expected_state
        if preferred.actual_state is None and candidate.actual_state is not None:
            preferred.actual_state = candidate.actual_state
        if preferred.missing_state is None and candidate.missing_state is not None:
            preferred.missing_state = candidate.missing_state
        if preferred.extra_state is None and candidate.extra_state is not None:
            preferred.extra_state = candidate.extra_state
        if not preferred.explanation and candidate.explanation:
            preferred.explanation = candidate.explanation
        if not preferred.root_cause and candidate.root_cause:
            preferred.root_cause = candidate.root_cause
        preferred.affected_variables = sorted(set(preferred.affected_variables + candidate.affected_variables))
        preferred.affected_lines = sorted(set(preferred.affected_lines + candidate.affected_lines))
        preferred.evidence = {**candidate.evidence, **preferred.evidence}
        if _SEVERITY_ORDER.get(candidate.severity, 0) > _SEVERITY_ORDER.get(preferred.severity, 0):
            preferred.severity = candidate.severity
        return preferred

    def _richness(self, divergence: Divergence) -> tuple[int, int, int, int]:
        return (
            _SEVERITY_ORDER.get(divergence.severity, 0),
            1 if divergence.causal_chain else 0,
            1 if divergence.expected_state is not None else 0,
            1 if divergence.actual_state is not None else 0,
        )

    def _enrich_divergence(self, divergence: Divergence, trace, intent, expectation) -> Divergence:
        step = self._step_for_line(trace, divergence.first_occurrence_line, divergence.symptom_line)
        if step is not None and divergence.actual_state is None:
            divergence.actual_state = step.variable_snapshot

        divergence.divergence_point = (
            f"step {step.step_id} at line {step.lineno}" if step else f"line {divergence.first_occurrence_line}"
        )

        if not divergence.causal_chain and step:
            divergence.causal_chain = [
                CausalStep(
                    step_index=step.step_id,
                    description=step.description,
                    lineno=step.lineno,
                    variable_state=step.variable_snapshot,
                    why_this_matters=divergence.algorithm_context,
                )
            ]

        if divergence.expected_state is None:
            divergence.expected_state = self._expected_state_from_checkpoints(expectation, divergence.first_occurrence_line)

        if not divergence.explanation:
            divergence.explanation = self._build_explanation(divergence)
        if not divergence.root_cause:
            divergence.root_cause = self._build_root_cause(divergence, step)

        return divergence

    def _step_for_line(self, trace, first_line: int, symptom_line: int):
        steps = getattr(trace, "steps", []) or []
        for line in (first_line, symptom_line):
            for step in steps:
                if step.lineno == line:
                    return step
        return None

    def _expected_state_from_checkpoints(self, expectation, line: int) -> Dict[str, Any]:
        checkpoints = getattr(expectation, "critical_checkpoints", []) or []
        for checkpoint in checkpoints:
            if checkpoint.program_point.lineno == line:
                return {
                    "condition": checkpoint.condition,
                    "expected_values": checkpoint.expected_values,
                }
        return {}

    def _build_explanation(self, divergence: Divergence) -> str:
        parts = [
            divergence.actual_behavior,
            divergence.algorithm_context,
        ]
        if divergence.expected_state is not None:
            parts.append(f"Expected state: {divergence.expected_state}.")
        if divergence.actual_state is not None:
            parts.append(f"Actual state: {divergence.actual_state}.")
        if divergence.missing_state is not None:
            parts.append(f"Missing state: {divergence.missing_state}.")
        return " ".join(part for part in parts if part)

    def _build_root_cause(self, divergence: Divergence, step) -> str:
        if step is not None:
            return f"{divergence.type} begins when step {step.step_id} executes `{step.code_snippet or step.code_line or f'line {step.lineno}'}`."
        return f"{divergence.type} begins at line {divergence.first_occurrence_line}."
