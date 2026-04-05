from __future__ import annotations

from typing import Any

from backend.services.execution_engine import serialize_value


def _diff_locals(prev: dict[str, Any], curr: dict[str, Any]) -> dict[str, Any]:
    added: dict[str, Any] = {}
    removed: dict[str, Any] = {}
    changed: dict[str, Any] = {}
    mutations: list[dict[str, Any]] = []

    prev_keys = set(prev.keys())
    curr_keys = set(curr.keys())

    for key in curr_keys - prev_keys:
        added[key] = curr[key]
    for key in prev_keys - curr_keys:
        removed[key] = prev[key]

    for key in prev_keys & curr_keys:
        prev_val = prev[key]
        curr_val = curr[key]
        if isinstance(prev_val, list) and isinstance(curr_val, list):
            if len(curr_val) != len(prev_val):
                mutations.append(
                    {
                        "type": "list_length_change",
                        "variable": key,
                        "from": len(prev_val),
                        "to": len(curr_val),
                        "delta": len(curr_val) - len(prev_val),
                        "added_items": curr_val[len(prev_val) :]
                        if len(curr_val) > len(prev_val)
                        else [],
                    }
                )
        if isinstance(prev_val, dict) and isinstance(curr_val, dict):
            if len(curr_val) != len(prev_val):
                mutations.append(
                    {
                        "type": "dict_size_change",
                        "variable": key,
                        "from": len(prev_val),
                        "to": len(curr_val),
                        "delta": len(curr_val) - len(prev_val),
                    }
                )
        if isinstance(prev_val, set) and isinstance(curr_val, set):
            if len(curr_val) != len(prev_val):
                mutations.append(
                    {
                        "type": "set_size_change",
                        "variable": key,
                        "from": len(prev_val),
                        "to": len(curr_val),
                        "delta": len(curr_val) - len(prev_val),
                    }
                )

        if serialize_value(prev_val) != serialize_value(curr_val):
            changed[key] = {"from": prev_val, "to": curr_val}

    return {
        "added": added,
        "removed": removed,
        "changed": changed,
        "mutations": mutations,
    }


def build_state_model(
    execution_trace: list[dict[str, Any]], ir: dict[str, Any]
) -> dict[str, Any]:
    loop_lines = {loop.get("lineno") for loop in ir.get("loops", []) if loop.get("lineno")}
    iteration_context: dict[int, int] = {}
    call_stack: list[dict[str, Any]] = []
    heap_objects: dict[str, Any] = {}

    previous_locals_by_frame: dict[int, dict[str, Any]] = {}
    semantic_trace: list[dict[str, Any]] = []

    for entry in execution_trace:
        frame_id = entry.get("frame_id")
        event = entry.get("event")
        func = entry.get("func") or "<module>"
        line = entry.get("line") or 0
        locals_snapshot = entry.get("locals", {})

        if event == "call":
            call_stack.append(
                {
                    "frame_id": frame_id,
                    "function": func,
                    "line": line,
                }
            )
        elif event in {"return", "exception"}:
            if call_stack and call_stack[-1].get("frame_id") == frame_id:
                call_stack.pop()

        if event == "line" and line in loop_lines:
            iteration_context[line] = iteration_context.get(line, 0) + 1

        prev_locals = previous_locals_by_frame.get(frame_id, {})
        state_diff = _diff_locals(prev_locals, locals_snapshot)
        previous_locals_by_frame[frame_id] = locals_snapshot

        for name, value in locals_snapshot.items():
            if isinstance(value, (list, dict, set)):
                heap_objects[name] = {
                    "type": type(value).__name__,
                    "size": len(value),
                    "owner": name,
                    "preview": serialize_value(value),
                }

        state = {
            "variables": locals_snapshot,
            "call_stack": call_stack.copy(),
            "heap_objects": heap_objects.copy(),
            "iteration_context": iteration_context.copy(),
        }

        semantic_trace.append(
            {
                "step": entry.get("step"),
                "line": line,
                "event": event,
                "func": func,
                "locals": locals_snapshot,
                "value": entry.get("value"),
                "state": state,
                "state_diff": state_diff,
                "iteration": iteration_context.get(line),
                "stack_depth": entry.get("stack_depth", 0),
            }
        )

    return {
        "semantic_trace": semantic_trace,
        "state": {
            "variables": semantic_trace[-1]["locals"] if semantic_trace else {},
            "call_stack": call_stack,
            "heap_objects": heap_objects,
            "iteration_context": iteration_context,
        },
    }
