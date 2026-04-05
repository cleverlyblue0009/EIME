from __future__ import annotations

import ast
import operator
import uuid
from typing import Any, Dict, List, Optional, Sequence

from backend.api.models import ExecutionStep, FunctionCall, LoopSummary, NormalizedTrace
from backend.execution.snapshot_manager import clone_snapshot

_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}
_FOCUS_HINTS = [
    "i",
    "j",
    "k",
    "left",
    "right",
    "low",
    "high",
    "mid",
    "queue",
    "visited",
    "dp",
    "memo",
    "heap",
    "result",
    "ans",
    "dist",
]


def normalize_trace(trace_events: List[Any], parse_result: Dict[str, Any]) -> NormalizedTrace:
    steps: List[ExecutionStep] = []
    loop_summaries: List[LoopSummary] = []
    function_calls: List[FunctionCall] = []
    path_taken: List[str] = []

    source_lines = (parse_result.get("source", "") if parse_result else "").splitlines()
    line_index = parse_result.get("line_index", {}) if parse_result else {}
    loops = parse_result.get("loops", []) if parse_result else []

    loop_counts: Dict[int, int] = {loop["header_line"]: 0 for loop in loops}
    loop_snapshots: Dict[int, List[Dict[str, Any]]] = {loop["header_line"]: [] for loop in loops}
    loop_mutations: Dict[int, set[str]] = {loop["header_line"]: set() for loop in loops}
    loop_step_ids: Dict[int, List[int]] = {loop["header_line"]: [] for loop in loops}
    loop_function_context: Dict[int, str] = {}

    active_calls: List[tuple[int, FunctionCall]] = []
    active_function_names: List[str] = []
    pending_lines: Dict[int, Any] = {}
    frame_recursion_depth: Dict[int, int] = {}
    last_step_for_frame: Dict[int, int] = {}

    step_counter = 0
    max_recursion_depth = 0

    def next_step_id() -> int:
        nonlocal step_counter
        step_counter += 1
        return step_counter

    def append_step(step: ExecutionStep, frame_id: Optional[int]) -> None:
        if step.step_id <= 0:
            step.step_id = next_step_id()
        steps.append(step)
        path_taken.append(f"step-{step.step_id}")
        if frame_id is not None:
            last_step_for_frame[frame_id] = step.step_id
        if step.group_id and step.group_id.startswith("loop:"):
            try:
                header_line = int(step.group_id.split(":", 1)[1])
            except Exception:
                header_line = None
            if header_line is not None and header_line in loop_step_ids:
                loop_step_ids[header_line].append(step.step_id)

    def finalize_line_step(line_event: Any, next_event: Optional[Any]) -> None:
        frame_id = getattr(line_event, "frame_id", None)
        pre_snapshot = clone_snapshot(getattr(line_event, "locals_snapshot", {}) or {})
        post_snapshot = (
            clone_snapshot(getattr(next_event, "locals_snapshot", {}) or {})
            if next_event is not None
            else clone_snapshot(pre_snapshot)
        )
        line_info = line_index.get(line_event.lineno, {})
        active_loop = _innermost_loop(loops, line_event.lineno)
        loop_iteration: Optional[int] = None
        operation = line_info.get("operation") or "line"

        if active_loop is not None and operation == "loop_header":
            loop_counts[active_loop["header_line"]] += 1
            loop_iteration = loop_counts[active_loop["header_line"]]
            loop_snapshots[active_loop["header_line"]].append(clone_snapshot(post_snapshot))
            if line_event.function_name and line_event.function_name != "<module>":
                loop_function_context.setdefault(active_loop["header_line"], line_event.function_name)
        elif active_loop is not None:
            loop_iteration = loop_counts[active_loop["header_line"]] or None

        deltas = _compute_deltas(pre_snapshot, post_snapshot)
        if active_loop is not None:
            loop_mutations[active_loop["header_line"]].update(deltas.keys())

        recursion_count = frame_recursion_depth.get(frame_id or -1, 1 if line_event.function_name != "<module>" else 0)
        context = _context_for_step(line_event.function_name, active_loop, recursion_count)
        function_context = line_event.function_name
        resolved_reads = [
            _resolve_access_template(template, pre_snapshot)
            for template in line_info.get("read_accesses", [])
        ]
        resolved_writes = [
            _resolve_access_template(template, post_snapshot)
            for template in line_info.get("write_accesses", [])
        ]
        return_value = getattr(next_event, "return_value", None) if next_event and next_event.event_type == "return" else None
        group_id = _group_id(active_loop, line_event.function_name)
        focus_variables = _focus_variables(post_snapshot, resolved_writes, resolved_reads)

        step = ExecutionStep(
            step_id=next_step_id(),
            lineno=line_event.lineno,
            description=_build_line_step_description(
                line_event,
                pre_snapshot,
                post_snapshot,
                line_info,
                loop_iteration,
                return_value,
            ),
            variable_deltas=deltas,
            context=context,
            loop_iteration=loop_iteration,
            function_name=line_event.function_name,
            parent_step_id=last_step_for_frame.get(frame_id) if frame_id is not None else None,
            event_type="line",
            code_line=line_info.get("code_line") or _line_text(source_lines, line_event.lineno),
            variable_snapshot=post_snapshot,
            operation=operation,
            explanation=line_info.get("explanation") or _fallback_explanation(line_event, line_info),
            algorithm_role=_algorithm_role(line_info, context),
            reads=line_info.get("reads", []),
            read_accesses=resolved_reads,
            writes=line_info.get("writes", []),
            write_accesses=resolved_writes,
            code_snippet=(line_info.get("code_line") or _line_text(source_lines, line_event.lineno)).strip(),
            variables=clone_snapshot(post_snapshot),
            operation_type=operation,
            iteration_index=loop_iteration,
            function_context=function_context,
            data_dependencies=list(dict.fromkeys(resolved_reads)),
            focus_variables=focus_variables,
            group_id=group_id,
            timestamp_ns=getattr(line_event, "timestamp_ns", None),
            scope_depth=max((getattr(line_event, "call_stack_depth", 1) or 1) - 1, 0),
            scope_event="step",
            scope_label=function_context if function_context and function_context != "<module>" else group_id,
        )
        append_step(step, frame_id)

    for event in trace_events:
        frame_id = getattr(event, "frame_id", None)
        max_recursion_depth = max(max_recursion_depth, getattr(event, "call_stack_depth", 0) or 0)

        if frame_id is not None and event.event_type in {"line", "return", "exception"} and frame_id in pending_lines:
            finalize_line_step(pending_lines.pop(frame_id), event)

        if event.event_type == "call":
            function_name = event.function_name
            is_module = function_name == "<module>"
            recursion_depth = active_function_names.count(function_name) + 1 if not is_module else 0
            if frame_id is not None:
                frame_recursion_depth[frame_id] = recursion_depth

            call = FunctionCall(
                call_id=str(uuid.uuid4()),
                function_name=function_name,
                call_site_line=event.lineno,
                arguments=clone_snapshot(event.locals_snapshot),
                return_value=None,
                child_calls=[],
                is_recursive=function_name in active_function_names,
                recursion_depth=getattr(event, "call_stack_depth", 0) or recursion_depth,
            )
            if active_calls:
                active_calls[-1][1].child_calls.append(call.call_id)
            active_calls.append((frame_id or -1, call))
            function_calls.append(call)

            if not is_module:
                append_step(_build_call_step(event, source_lines, recursion_depth), frame_id)
                active_function_names.append(function_name)
            continue

        if event.event_type == "line":
            if frame_id is not None:
                pending_lines[frame_id] = event
            continue

        if event.event_type == "exception":
            append_step(_build_exception_step(event, source_lines, last_step_for_frame.get(frame_id or -1)), frame_id)

        if event.event_type == "return":
            if active_calls and active_calls[-1][0] == (frame_id or -1):
                active_calls[-1][1].return_value = clone_snapshot(event.return_value) if isinstance(event.return_value, dict) else event.return_value
                active_calls.pop()
            if event.function_name != "<module>":
                append_step(_build_return_exit_step(event, source_lines, last_step_for_frame.get(frame_id or -1)), frame_id)
            if event.function_name != "<module>" and active_function_names and active_function_names[-1] == event.function_name:
                active_function_names.pop()
            if frame_id is not None:
                frame_recursion_depth.pop(frame_id, None)

    for pending_event in sorted(pending_lines.values(), key=lambda item: item.event_id):
        finalize_line_step(pending_event, None)

    for loop in loops:
        header_line = loop["header_line"]
        loop_summaries.append(
            LoopSummary(
                loop_id=f"loop-{header_line}",
                header_line=header_line,
                iteration_count=loop_counts.get(header_line, 0),
                loop_variable=loop.get("loop_variable"),
                exit_reason="exhausted",
                variables_mutated=sorted(loop_mutations.get(header_line, set())),
                per_iteration_snapshots=loop_snapshots.get(header_line, []),
                iteration_step_ids=loop_step_ids.get(header_line, []),
                function_context=loop_function_context.get(header_line),
            )
        )

    final_state = clone_snapshot(steps[-1].variable_snapshot) if steps else _final_snapshot(trace_events)

    return NormalizedTrace(
        steps=steps,
        loop_summaries=loop_summaries,
        function_calls=function_calls,
        path_taken=path_taken,
        final_state=final_state,
        total_steps=len(steps),
        max_recursion_depth=max_recursion_depth,
    )


def _build_call_step(event: Any, source_lines: Sequence[str], recursion_depth: int) -> ExecutionStep:
    snapshot_plain = clone_snapshot(event.locals_snapshot)
    args_preview = ", ".join(
        f"{name}={_short_value(value)}" for name, value in list(snapshot_plain.items())[:3]
    )
    suffix = f"({args_preview})" if args_preview else "()"
    function_context = event.function_name
    return ExecutionStep(
        step_id=0,
        lineno=event.lineno,
        description=f"call {event.function_name}{suffix}",
        variable_deltas={},
        context="RECURSION" if recursion_depth > 1 else "FUNCTION",
        loop_iteration=None,
        function_name=function_context,
        parent_step_id=None,
        event_type="call",
        code_line=_line_text(source_lines, event.lineno),
        variable_snapshot=snapshot_plain,
        operation="call",
        explanation="Enter a new function frame and bind the incoming arguments.",
        algorithm_role="function_entry",
        reads=[],
        read_accesses=[],
        writes=[],
        write_accesses=[],
        code_snippet=_line_text(source_lines, event.lineno).strip(),
        variables=clone_snapshot(snapshot_plain),
        operation_type="call",
        iteration_index=None,
        function_context=function_context,
        data_dependencies=[],
        focus_variables=_focus_variables(snapshot_plain, [], list(snapshot_plain.keys())),
        group_id=_group_id(None, function_context),
        timestamp_ns=getattr(event, "timestamp_ns", None),
        scope_depth=max((getattr(event, "call_stack_depth", 1) or 1) - 1, 0),
        scope_event="enter",
        scope_label=function_context,
    )


def _build_exception_step(event: Any, source_lines: Sequence[str], parent_step_id: Optional[int]) -> ExecutionStep:
    snapshot_plain = clone_snapshot(event.locals_snapshot)
    function_context = event.function_name
    return ExecutionStep(
        step_id=0,
        lineno=event.lineno,
        description=f"exception: {event.exception_info or 'runtime error'}",
        variable_deltas={},
        context="FUNCTION" if event.function_name != "<module>" else "MAIN",
        loop_iteration=None,
        function_name=function_context,
        parent_step_id=parent_step_id,
        event_type="exception",
        code_line=_line_text(source_lines, event.lineno),
        variable_snapshot=snapshot_plain,
        operation="exception",
        explanation="Execution raises an exception at this program point.",
        algorithm_role="exception_state",
        reads=[],
        read_accesses=[],
        writes=[],
        write_accesses=[],
        code_snippet=_line_text(source_lines, event.lineno).strip(),
        variables=clone_snapshot(snapshot_plain),
        operation_type="exception",
        iteration_index=None,
        function_context=function_context,
        data_dependencies=[],
        focus_variables=_focus_variables(snapshot_plain, [], list(snapshot_plain.keys())),
        group_id=_group_id(None, function_context),
        timestamp_ns=getattr(event, "timestamp_ns", None),
        scope_depth=max((getattr(event, "call_stack_depth", 1) or 1) - 1, 0),
        scope_event="exception",
        scope_label=function_context,
    )


def _build_return_exit_step(event: Any, source_lines: Sequence[str], parent_step_id: Optional[int]) -> ExecutionStep:
    snapshot_plain = clone_snapshot(event.locals_snapshot)
    function_context = event.function_name
    return ExecutionStep(
        step_id=0,
        lineno=event.lineno,
        description=f"exit {function_context} -> {_short_value(event.return_value)}",
        variable_deltas={},
        context="RECURSION" if (getattr(event, "call_stack_depth", 0) or 0) > 1 else "FUNCTION",
        loop_iteration=None,
        function_name=function_context,
        parent_step_id=parent_step_id,
        event_type="return",
        code_line=_line_text(source_lines, event.lineno),
        variable_snapshot=snapshot_plain,
        operation="return",
        explanation="Leave the current function scope and hand the return value to the caller.",
        algorithm_role="function_exit",
        reads=[],
        read_accesses=[],
        writes=[],
        write_accesses=[],
        code_snippet=_line_text(source_lines, event.lineno).strip(),
        variables=clone_snapshot(snapshot_plain),
        operation_type="return",
        iteration_index=None,
        function_context=function_context,
        data_dependencies=[],
        focus_variables=_focus_variables(snapshot_plain, [], list(snapshot_plain.keys())),
        group_id=_group_id(None, function_context),
        timestamp_ns=getattr(event, "timestamp_ns", None),
        scope_depth=max((getattr(event, "call_stack_depth", 1) or 1) - 1, 0),
        scope_event="exit",
        scope_label=function_context,
    )


def _compute_deltas(before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    deltas: Dict[str, Dict[str, Any]] = {}
    for key in sorted(set(before.keys()).union(after.keys())):
        if before.get(key) != after.get(key):
            deltas[key] = {"from": before.get(key), "to": after.get(key)}
    return deltas


def _final_snapshot(trace_events: Sequence[Any]) -> Dict[str, Any]:
    if not trace_events:
        return {}
    return clone_snapshot(getattr(trace_events[-1], "locals_snapshot", {}) or {})


def _line_text(source_lines: Sequence[str], lineno: int) -> str:
    if 0 < lineno <= len(source_lines):
        return source_lines[lineno - 1]
    return ""


def _context_for_step(function_name: str, active_loop: Optional[Dict[str, Any]], recursion_count: int) -> str:
    if recursion_count > 1 and function_name and function_name != "<module>":
        return "RECURSION"
    if active_loop is not None:
        return "LOOP"
    if function_name and function_name != "<module>":
        return "FUNCTION"
    return "MAIN"


def _fallback_explanation(event: Any, line_info: Dict[str, Any]) -> str:
    if line_info.get("operation") == "return":
        return "Return the computed result to the caller."
    if line_info.get("operation") == "loop_header":
        return "Advance loop control and decide whether another iteration should run."
    if line_info.get("operation") == "branch":
        return "Evaluate a condition that controls which path executes next."
    return "Execute the current line and update program state."


def _algorithm_role(line_info: Dict[str, Any], context: str) -> str:
    writes = line_info.get("writes", [])
    reads = line_info.get("reads", [])
    names = writes + reads
    if any(name in {"dp", "memo", "cache"} for name in names):
        return "dynamic_programming_state"
    if any(name in {"left", "right", "l", "r", "low", "high"} for name in names):
        return "pointer_state_update"
    if any(name in {"queue", "q", "deque"} for name in names):
        return "queue_frontier_update"
    if any(name in {"stack", "stk"} for name in names):
        return "stack_state_update"
    if any(name in {"visited", "seen"} for name in names):
        return "visited_state_update"
    if any(name in {"heap"} for name in names):
        return "heap_state_update"
    if context == "LOOP" and writes:
        return "loop_iteration_update"
    if line_info.get("operation") == "branch":
        return "control_decision"
    if line_info.get("operation") == "return":
        return "result_extraction"
    if line_info.get("operation") == "loop_header":
        return "loop_control"
    return "execution_step"


def _build_line_step_description(
    event: Any,
    pre_snapshot: Dict[str, Any],
    post_snapshot: Dict[str, Any],
    line_info: Dict[str, Any],
    loop_iteration: Optional[int],
    return_value: Any,
) -> str:
    operation = line_info.get("operation")
    if operation in {"assignment", "mutation"}:
        rendered_writes = line_info.get("write_accesses", [])
        if rendered_writes:
            target = _resolve_access_template(rendered_writes[0], post_snapshot)
            value = _value_for_access(target, post_snapshot)
            if value is not None:
                return f"{target} = {_short_value(value)}"
            return target
        changed = list(_compute_deltas(pre_snapshot, post_snapshot).items())
        if changed:
            name, delta = changed[0]
            return f"{name} = {_short_value(delta.get('to'))}"
    if operation == "return":
        return f"return {_short_value(return_value)}" if return_value is not None else "return"
    if operation == "loop_header":
        code_line = (line_info.get("code_line") or "").strip()
        if loop_iteration:
            return f"iter {loop_iteration}: {code_line}"
        return code_line or f"loop at line {event.lineno}"
    if operation == "branch":
        condition = line_info.get("condition") or (line_info.get("code_line") or "").strip()
        return f"check {condition}"
    code_line = (line_info.get("code_line") or "").strip()
    return code_line or f"line {event.lineno}"


def _resolve_access_template(template: str, snapshot: Dict[str, Any]) -> str:
    template = template.strip()
    if "[" in template and template.endswith("]"):
        base, _, index_expr = template.partition("[")
        index_expr = index_expr[:-1]
        resolved_index = _safe_eval(index_expr, snapshot)
        if resolved_index is not None:
            return f"{base}[{resolved_index}]"
    return template


def _value_for_access(access: str, snapshot: Dict[str, Any]) -> Any:
    access = access.strip()
    if access in snapshot:
        return snapshot.get(access)
    if "[" in access and access.endswith("]"):
        base, _, index_text = access.partition("[")
        container = snapshot.get(base)
        resolved_index = _safe_eval(index_text[:-1], snapshot)
        try:
            if isinstance(container, dict):
                return container.get(resolved_index)
            if isinstance(container, list) and isinstance(resolved_index, int):
                if 0 <= resolved_index < len(container):
                    return container[resolved_index]
        except Exception:
            return None
    return None


def _short_value(value: Any) -> str:
    text = repr(value)
    if len(text) > 60:
        return text[:57] + "..."
    return text


def _innermost_loop(loops: List[Dict[str, Any]], lineno: int) -> Optional[Dict[str, Any]]:
    matches = [
        loop
        for loop in loops
        if loop.get("header_line", 0) <= lineno <= loop.get("end_line", loop.get("header_line", 0))
    ]
    if not matches:
        return None
    return min(matches, key=lambda loop: loop.get("end_line", loop.get("header_line", 0)) - loop.get("header_line", 0))


def _safe_eval(expression: str, snapshot: Dict[str, Any]) -> Any:
    try:
        parsed = ast.parse(expression, mode="eval")
        return _eval_expr(parsed.body, snapshot)
    except Exception:
        return None


def _eval_expr(node: ast.AST, snapshot: Dict[str, Any]) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        return snapshot.get(node.id)
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        left = _eval_expr(node.left, snapshot)
        right = _eval_expr(node.right, snapshot)
        if left is None or right is None:
            return None
        return _BIN_OPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        operand = _eval_expr(node.operand, snapshot)
        if operand is None:
            return None
        return _UNARY_OPS[type(node.op)](operand)
    return None


def _focus_variables(snapshot: Dict[str, Any], write_accesses: List[str], read_accesses: List[str]) -> Dict[str, Any]:
    preview: Dict[str, Any] = {}
    ordered_accesses = write_accesses + read_accesses
    for access in ordered_accesses:
        base = access.split("[", 1)[0].split(".", 1)[0]
        if base in snapshot and base not in preview:
            preview[base] = snapshot[base]
        if access in snapshot and access not in preview:
            preview[access] = snapshot[access]
        if len(preview) >= 4:
            return preview

    for key in _FOCUS_HINTS:
        if key in snapshot and key not in preview:
            preview[key] = snapshot[key]
        if len(preview) >= 4:
            return preview

    for key, value in snapshot.items():
        if key not in preview:
            preview[key] = value
        if len(preview) >= 4:
            break
    return preview


def _group_id(active_loop: Optional[Dict[str, Any]], function_name: Optional[str]) -> str:
    if active_loop is not None:
        return f"loop:{active_loop['header_line']}"
    if function_name and function_name != "<module>":
        return f"fn:{function_name}"
    return "main"
