from __future__ import annotations

from typing import Any, Dict, List

from backend.api.models import VariableRole


class VariableRoleInferrer:
    def infer(self, vdg, trace, intent_pattern, pattern_hints) -> Dict[str, VariableRole]:
        variables = {}
        steps = trace.steps if hasattr(trace, "steps") else trace
        values_by_var: Dict[str, List[Any]] = {}
        final_state = {}

        if hasattr(trace, "final_state"):
            for key, value in trace.final_state.items():
                final_state[key] = value

        for step in steps:
            snapshot = {}
            if hasattr(step, "variable_deltas"):
                for key, delta in step.variable_deltas.items():
                    snapshot[key] = delta.get("to")
            for key, value in snapshot.items():
                values_by_var.setdefault(key, []).append(value)

        max_list_len = 0
        for vals in values_by_var.values():
            for v in vals:
                if isinstance(v, list):
                    max_list_len = max(max_list_len, len(v))

        def is_monotone(vals: List[Any], increasing: bool) -> bool:
            nums = [v for v in vals if isinstance(v, (int, float))]
            if len(nums) < 2:
                return False
            if increasing:
                return all(b >= a for a, b in zip(nums, nums[1:]))
            return all(b <= a for a, b in zip(nums, nums[1:]))

        def increments_by_one(vals: List[Any]) -> bool:
            nums = [v for v in vals if isinstance(v, int)]
            if len(nums) < 2:
                return False
            return all((b - a) == 1 for a, b in zip(nums, nums[1:]))

        def is_boolean(vals: List[Any]) -> bool:
            observed = False
            for v in vals:
                if v is None:
                    continue
                observed = True
                if isinstance(v, bool):
                    continue
                if isinstance(v, int) and v in (0, 1):
                    continue
                return False
            return observed

        def is_2d_list(vals: List[Any]) -> bool:
            for v in vals:
                if isinstance(v, list) and v and all(isinstance(x, list) for x in v):
                    return True
            return False

        def is_graph_adj(vals: List[Any]) -> bool:
            for v in vals:
                if isinstance(v, dict):
                    if v and all(isinstance(val, list) for val in v.values()):
                        return True
                if isinstance(v, list) and v and all(isinstance(x, list) for x in v):
                    return True
            return False

        def is_dict_keyed_by_state(vals: List[Any]) -> bool:
            for v in vals:
                if isinstance(v, dict) and v:
                    key = next(iter(v.keys()))
                    if isinstance(key, tuple):
                        return True
            return False

        def is_collection_growing(vals: List[Any]) -> bool:
            sizes = []
            for v in vals:
                if isinstance(v, (list, dict, set, tuple)):
                    sizes.append(len(v))
            if len(sizes) < 2:
                return False
            return any(b > a for a, b in zip(sizes, sizes[1:]))

        def is_never_modified(vals: List[Any]) -> bool:
            return len(set(map(str, vals))) <= 1

        role_rules = {
            "ACCUMULATOR": ["name_matches_result_pattern", "is_returned_at_end"],
            "WINDOW_START": ["name_matches_left_pattern"],
            "WINDOW_END": ["name_matches_right_pattern"],
            "MEMO_TABLE": ["name_matches_dp_pattern", "is_dict_keyed_by_state"],
            "VISITED_SET": ["name_matches_visited_pattern"],
            "RESULT_CANDIDATE": ["name_matches_result_pattern"],
            "LOOP_COUNTER": ["increments_by_one"],
            "POINTER_LEFT": ["name_matches_left_pattern"],
            "POINTER_RIGHT": ["name_matches_right_pattern"],
            "FAST_POINTER": ["name_matches_right_pattern"],
            "SLOW_POINTER": ["name_matches_left_pattern"],
            "STACK_DS": ["name_matches_stack_pattern"],
            "QUEUE_DS": ["name_matches_queue_pattern"],
            "HEAP_DS": ["is_used_in_heap_operation"],
            "PARENT_MAP": ["name_matches_left_pattern"],
            "DISTANCE_MAP": ["name_matches_result_pattern"],
            "IN_DEGREE": ["name_matches_result_pattern"],
            "DP_TABLE": ["name_matches_dp_pattern"],
            "FREQUENCY_MAP": ["name_matches_result_pattern"],
            "GRAPH_ADJ": ["is_graph_adjacency"],
            "MONOTONIC_STACK": ["name_matches_stack_pattern"],
            "MONOTONIC_QUEUE": ["name_matches_queue_pattern"],
            "TRIE_NODE": ["name_matches_result_pattern"],
            "UNION_FIND_PARENT": ["name_matches_left_pattern"],
            "BIT_MASK": ["is_boolean_or_binary"],
            "LEFT_BOUND": ["name_matches_left_pattern"],
            "RIGHT_BOUND": ["name_matches_right_pattern"],
            "MID_POINTER": ["name_matches_result_pattern"],
            "COMPARATOR": ["name_matches_result_pattern"],
            "UNKNOWN": [],
        }

        for var_name, vals in values_by_var.items():
            if pattern_hints and var_name in pattern_hints:
                role = pattern_hints[var_name][0]
                variables[var_name] = VariableRole(
                    variable_name=var_name,
                    role=role,
                    confidence=0.9,
                    evidence="pattern hint",
                )
                continue

            features = {
                "is_monotone_increasing": is_monotone(vals, True),
                "is_monotone_decreasing": is_monotone(vals, False),
                "is_bounded_by_array_length": (
                    max_list_len
                    and max([v for v in vals if isinstance(v, (int, float))] or [0])
                    <= max_list_len
                ),
                "is_always_non_negative": all(isinstance(v, (int, float)) and v >= 0 for v in vals if v is not None),
                "increments_by_one": increments_by_one(vals),
                "is_collection_growing": is_collection_growing(vals),
                "is_collection_element_lookup_key": False,
                "is_returned_at_end": var_name in final_state,
                "is_reset_in_outer_loop": False,
                "is_compared_with_other_pointer": False,
                "tracks_another_variable": False,
                "is_used_in_heap_operation": var_name in (vdg or {}).get("dependencies", {}),
                "is_dict_keyed_by_state": is_dict_keyed_by_state(vals),
                "name_matches_left_pattern": var_name in {"l", "left", "lo", "start", "begin", "i"},
                "name_matches_right_pattern": var_name in {"r", "right", "hi", "end", "j", "fast"},
                "name_matches_result_pattern": var_name in {"res", "result", "ans", "output", "ret"},
                "name_matches_dp_pattern": var_name in {"dp", "memo", "cache", "f", "g"},
                "name_matches_visited_pattern": var_name in {"visited", "seen", "used"},
                "name_matches_stack_pattern": var_name in {"stack", "stk"},
                "name_matches_queue_pattern": var_name in {"queue", "q", "deque"},
                "is_boolean_or_binary": is_boolean(vals),
                "is_2d_list": is_2d_list(vals),
                "is_never_modified_after_init": is_never_modified(vals),
                "difference_from_partner_is_constant": False,
                "is_graph_adjacency": is_graph_adj(vals),
            }

            best_role = "UNKNOWN"
            best_score = 0.0
            best_evidence = ""
            for role, required in role_rules.items():
                if not required:
                    continue
                matches = sum(1 for feat in required if features.get(feat))
                score = matches / max(len(required), 1)
                if score > best_score:
                    best_score = score
                    best_role = role
                    best_evidence = ", ".join([feat for feat in required if features.get(feat)])

            if best_score < 0.4:
                best_role = "UNKNOWN"
                best_evidence = "low confidence"

            variables[var_name] = VariableRole(
                variable_name=var_name,
                role=best_role,
                confidence=round(best_score, 2),
                evidence=best_evidence,
            )

        return variables
