from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple

from backend.api.models import Checkpoint, ExpectationModel, LineRef


class ExpectationGenerator:
    def generate(self, intent, normalized_trace, parse_result) -> ExpectationModel:
        expected_loop_counts: Dict[str, int] = {}
        expected_loop_count_formulas: Dict[str, str] = {}
        expected_variable_final_values: Dict[str, Any] = {}
        critical_checkpoints: List[Checkpoint] = []
        expected_output: Any = None
        expected_recursion_depth = None
        expected_memo_table_size = None

        n = self._infer_n(normalized_trace)
        k = self._infer_k(normalized_trace)

        if intent.inferred_algorithm == "sliding_window_fixed":
            expected_loop_count_formulas = {"main_loop": "len(arr) - k + 1"}
            header_line = self._loop_header(parse_result)
            arr_name, arr_value = self._infer_primary_sequence(normalized_trace)
            if n is not None and k is not None:
                expected_loop_counts = {"main_loop": max(n - k + 1, 0)}
            if isinstance(arr_value, list) and isinstance(k, int) and k > 0:
                expected_variable_final_values["expected_windows"] = [
                    {
                        "start": index,
                        "end": index + k - 1,
                        "values": arr_value[index : index + k],
                    }
                    for index in range(max(len(arr_value) - k + 1, 0))
                ]
            critical_checkpoints.append(
                Checkpoint(
                    program_point=LineRef(lineno=header_line),
                    condition="Every valid fixed-size window position must be evaluated exactly once.",
                    expected_values={
                        "loop_iterations": max(n - k + 1, 0) if n is not None and k is not None else "len(arr)-k+1",
                        "window_formula": f"{arr_name}[i:i+{k if k is not None else 'k'}]",
                    },
                    criticality="MUST",
                )
            )

        elif intent.inferred_algorithm == "binary_search_array":
            expected_loop_count_formulas = {"main_loop": "ceil(log2(n)) + 1"}
            if n is not None:
                expected_loop_counts = {"main_loop": int(math.ceil(math.log2(max(n, 1)))) + 1}
            critical_checkpoints.extend(
                [
                    Checkpoint(
                        program_point=LineRef(lineno=self._loop_header(parse_result)),
                        condition="The candidate interval remains inclusive until the final one-element case is tested.",
                        expected_values={"loop_condition": "low <= high"},
                        criticality="MUST",
                    ),
                    Checkpoint(
                        program_point=LineRef(lineno=self._loop_header(parse_result)),
                        condition="Each iteration discards at least one side of the interval.",
                        expected_values={"updates": ["low = mid + 1", "high = mid - 1"]},
                        criticality="MUST",
                    ),
                ]
            )

        elif intent.inferred_algorithm == "dp_1d_linear":
            if n is not None:
                expected_loop_counts = {"dp_loop": n}
                expected_variable_final_values["expected_state_indices"] = list(range(0, n + 1))
            expected_variable_final_values["state_progression_rule"] = "dp[i] depends only on earlier states dp[j] where j < i"
            critical_checkpoints.extend(
                [
                    Checkpoint(
                        program_point=LineRef(lineno=1),
                        condition="Base state is initialized before any recurrence transition.",
                        expected_values={"base_case": "initialized"},
                        criticality="MUST",
                    ),
                    Checkpoint(
                        program_point=LineRef(lineno=self._loop_header(parse_result)),
                        condition="Each DP transition uses only already-computed states.",
                        expected_values={"dependency_direction": "backward-only"},
                        criticality="MUST",
                    ),
                ]
            )

        elif intent.inferred_algorithm.startswith("bfs"):
            expected_loop_count_formulas = {"outer_loop": "V vertices processed"}
            expected_variable_final_values["frontier_rule"] = "Nodes are marked visited at enqueue time."
            critical_checkpoints.extend(
                [
                    Checkpoint(
                        program_point=LineRef(lineno=self._loop_header(parse_result)),
                        condition="The start node is visited before it enters the queue.",
                        expected_values={"visited_timing": "enqueue"},
                        criticality="MUST",
                    ),
                    Checkpoint(
                        program_point=LineRef(lineno=self._loop_header(parse_result)),
                        condition="Neighbors become visited as soon as they are scheduled.",
                        expected_values={"neighbor_visit_timing": "enqueue"},
                        criticality="MUST",
                    ),
                ]
            )

        elif intent.inferred_algorithm == "backtracking":
            expected_variable_final_values["path_rule"] = "Path state must be restored after every recursive branch."
            critical_checkpoints.extend(
                [
                    Checkpoint(
                        program_point=LineRef(lineno=self._loop_header(parse_result)),
                        condition="State is restored after recursion unwinds.",
                        expected_values={"restore": "present"},
                        criticality="MUST",
                    ),
                    Checkpoint(
                        program_point=LineRef(lineno=self._loop_header(parse_result)),
                        condition="Solutions are appended as immutable snapshots of the current path.",
                        expected_values={"append": "path[:]"},
                        criticality="MUST",
                    ),
                ]
            )

        elif intent.inferred_algorithm == "recursion_memo":
            if n is not None:
                expected_recursion_depth = n
            expected_memo_table_size = None if n is None else n + 1
            expected_variable_final_values["memo_rule"] = "Memo/cache must be checked before recursive expansion."
            critical_checkpoints.extend(
                [
                    Checkpoint(
                        program_point=LineRef(lineno=1),
                        condition="Base case returns immediately for the smallest subproblem.",
                        expected_values={"base_case": "present"},
                        criticality="MUST",
                    ),
                    Checkpoint(
                        program_point=LineRef(lineno=1),
                        condition="Memo table is consulted before recursive calls.",
                        expected_values={"memo_check": "pre-recursion"},
                        criticality="SHOULD",
                    ),
                ]
            )

        return ExpectationModel(
            expected_loop_counts=expected_loop_counts,
            expected_loop_count_formulas=expected_loop_count_formulas,
            expected_variable_final_values=expected_variable_final_values,
            expected_output=expected_output,
            critical_checkpoints=critical_checkpoints,
            expected_recursion_depth=expected_recursion_depth,
            expected_memo_table_size=expected_memo_table_size,
        )

    def _infer_n(self, normalized_trace) -> int | None:
        if not normalized_trace or not normalized_trace.final_state:
            return None
        for value in normalized_trace.final_state.values():
            v = value
            if isinstance(v, list):
                return len(v)
        return None

    def _infer_k(self, normalized_trace) -> int | None:
        if not normalized_trace or not normalized_trace.final_state:
            return None
        for key, value in normalized_trace.final_state.items():
            if key == "k":
                v = value
                if isinstance(v, int):
                    return v
        return None

    def _infer_primary_sequence(self, normalized_trace) -> Tuple[str, Any]:
        if not normalized_trace or not normalized_trace.final_state:
            return "arr", None
        for preferred in ("arr", "nums", "array", "values", "dp"):
            if preferred in normalized_trace.final_state:
                value = normalized_trace.final_state[preferred]
                plain = value
                if isinstance(plain, list):
                    return preferred, plain
        for key, value in normalized_trace.final_state.items():
            plain = value
            if isinstance(plain, list):
                return key, plain
        return "arr", None

    def _loop_header(self, parse_result) -> int:
        loops = parse_result.get("loops", []) if parse_result else []
        if loops:
            return loops[0].get("header_line", 1)
        return 1
