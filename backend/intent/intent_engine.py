from __future__ import annotations

from typing import Any, Dict, List

from backend.api.models import AlgorithmPhase, IntentModel
from backend.intent.pattern_registry import PatternRegistry
from backend.intent.variable_role_inferrer import VariableRoleInferrer


GOAL_MAP = {
    "sliding_window_fixed": "Find the best fixed-size contiguous window using an O(n) running update.",
    "sliding_window_variable": "Maintain a valid variable-size window while scanning the array once.",
    "binary_search_array": "Find a target in a sorted search space by halving the candidate interval.",
    "binary_search_answer_space": "Search the monotone answer boundary with a feasibility predicate.",
    "backtracking": "Enumerate valid choices recursively while restoring state after each branch.",
    "dp_1d_linear": "Build the answer from smaller 1D subproblems in index order.",
    "dp_1d_kadane": "Track the best subarray ending at each position and the global optimum.",
    "bfs_standard": "Traverse the graph layer by layer from the start node using a queue.",
    "dfs_recursive": "Explore a graph or tree recursively while preserving visited-state invariants.",
    "recursion_memo": "Solve overlapping recursive subproblems with memoized top-down recursion.",
    "union_find": "Maintain connected components with root-finding and near-constant merges.",
    "graph_mst": "Construct a minimum spanning tree by repeatedly taking the cheapest safe edge.",
    "matrix_traversal": "Visit matrix cells in a structured boundary-driven order without repeats.",
}


class IntentEngine:
    def __init__(self) -> None:
        self.registry = PatternRegistry()
        self.role_inferrer = VariableRoleInferrer()

    def analyze(
        self,
        parse_result: Dict[str, Any],
        normalized_trace: Any,
    ) -> IntentModel:
        cfg = parse_result.get("cfg", {}) if parse_result else {}
        vdg = parse_result.get("vdg", {}) if parse_result else {}
        call_graph = parse_result.get("call_graph", {}) if parse_result else {}
        var_names = parse_result.get("var_names", set()) if parse_result else set()
        imports = parse_result.get("imports", []) if parse_result else []

        pattern, confidence = self.registry.best_pattern(cfg, vdg, call_graph, var_names, imports)

        role_hints = pattern.get_variable_role_hints()
        variable_roles = self.role_inferrer.infer(vdg, normalized_trace, pattern, role_hints)

        invariants = pattern.get_invariants(variable_roles)

        complexity_map = {
            "sliding_window_fixed": ("O(n)", "O(1)"),
            "sliding_window_variable": ("O(n)", "O(1)"),
            "binary_search_array": ("O(log n)", "O(1)"),
            "binary_search_answer_space": ("O(log n)", "O(1)"),
            "merge_sort": ("O(n log n)", "O(n)"),
            "quick_sort_lomuto": ("O(n log n)", "O(log n)"),
            "dp_1d_linear": ("O(n)", "O(n)"),
            "dp_2d_grid": ("O(m*n)", "O(m*n)"),
            "bfs_standard": ("O(V+E)", "O(V)"),
            "dfs_recursive": ("O(V+E)", "O(V)"),
            "backtracking": ("O(branch^depth)", "O(depth)"),
            "recursion_memo": ("O(states)", "O(states)"),
            "union_find": ("O(alpha(n))", "O(n)"),
            "graph_mst": ("O(E log E)", "O(V)"),
            "matrix_traversal": ("O(m*n)", "O(1)"),
        }
        time_cx, space_cx = complexity_map.get(pattern.name, ("O(n)", "O(1)"))
        phases: List[AlgorithmPhase] = self._build_phases(parse_result, pattern.name, time_cx_hint=time_cx)

        programmer_goal = GOAL_MAP.get(
            pattern.name,
            f"Implement {pattern.name.replace('_', ' ')} while preserving its canonical invariants.",
        )

        return IntentModel(
            inferred_algorithm=pattern.name,
            algorithm_variant=pattern.variant,
            confidence=round(confidence, 2),
            programmer_goal=programmer_goal,
            invariants=invariants,
            expected_variable_roles=variable_roles,
            algorithm_phase_sequence=phases,
            known_pitfalls=pattern.get_known_pitfalls(),
            expected_time_complexity=time_cx,
            expected_space_complexity=space_cx,
            source="STRUCTURAL",
            llm_advisory={},
        )

    def _build_phases(self, parse_result: Dict[str, Any], pattern_name: str, time_cx_hint: str) -> List[AlgorithmPhase]:
        loops = parse_result.get("loops", []) if parse_result else []
        line_index = parse_result.get("line_index", {}) if parse_result else {}
        line_count = max(parse_result.get("line_count", 1), 1) if parse_result else 1
        phases: List[AlgorithmPhase] = []

        if loops:
            first_loop = min(loop["header_line"] for loop in loops)
            last_loop = max(loop.get("end_line", loop["header_line"]) for loop in loops)
            if first_loop > 1:
                phases.append(
                    AlgorithmPhase(
                        phase_name="Initialization",
                        start_line=1,
                        end_line=max(first_loop - 1, 1),
                        description="Initialize variables, data structures, and algorithm seed state.",
                        expected_complexity="O(1)",
                    )
                )
            phases.append(
                AlgorithmPhase(
                    phase_name="Core Execution",
                    start_line=first_loop,
                    end_line=last_loop,
                    description=f"Primary {pattern_name.replace('_', ' ')} traversal and state updates.",
                    expected_complexity=time_cx_hint,
                )
            )
            if last_loop < line_count:
                phases.append(
                    AlgorithmPhase(
                        phase_name="Result Extraction",
                        start_line=last_loop + 1,
                        end_line=line_count,
                        description="Finalize and return the computed answer after the main traversal.",
                        expected_complexity="O(1)",
                    )
                )
            return phases

        return [
            AlgorithmPhase(
                phase_name="Core Execution",
                start_line=min(line_index.keys(), default=1),
                end_line=line_count,
                description=f"Main {pattern_name.replace('_', ' ')} body without an explicit loop phase.",
                expected_complexity=time_cx_hint,
            )
        ]
