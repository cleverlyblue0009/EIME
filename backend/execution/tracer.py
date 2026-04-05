from __future__ import annotations

import sys
import time
from types import FrameType
from typing import Any, Dict, List

from backend.api.models import TraceEvent
from backend.execution.snapshot_manager import serialize_locals, serialize_value

USER_CODE_FILENAME = "<ime_user_code>"
MAX_TRACE_STEPS = 20_000


def trace_code(code: str, globals_dict: Dict[str, Any]) -> List[TraceEvent]:
    trace_events: List[TraceEvent] = []
    call_stack: List[int] = []
    recorded_returns: set[int] = set()
    event_id = 0

    def _trace(frame: FrameType, event: str, arg: Any) -> Any:
        nonlocal event_id
        if frame.f_code.co_filename != USER_CODE_FILENAME:
            return _trace
        if event not in {"call", "line", "return", "exception"}:
            return _trace
        if len(trace_events) >= MAX_TRACE_STEPS:
            return None

        frame_id = id(frame)
        func_name = frame.f_code.co_name
        if event == "call":
            call_stack.append(frame_id)

        if event == "return" and frame_id in recorded_returns:
            return _trace

        call_stack_depth = len(call_stack)
        event_id += 1
        trace_event = TraceEvent(
            event_id=event_id,
            timestamp_ns=time.perf_counter_ns(),
            event_type=event,
            lineno=frame.f_lineno,
            function_name=func_name,
            frame_id=frame_id,
            locals_snapshot=serialize_locals(frame.f_locals),
            call_stack_depth=call_stack_depth,
            loop_iteration=None,
            return_value=serialize_value(arg) if event == "return" else None,
            exception_info=repr(arg[1]) if event == "exception" and isinstance(arg, tuple) else None,
        )
        if event == "return":
            recorded_returns.add(frame_id)
        trace_events.append(trace_event)
        if event in {"return", "exception"} and call_stack and call_stack[-1] == frame_id:
            call_stack.pop()
        return _trace

    compiled = compile(code, USER_CODE_FILENAME, "exec")
    sys.settrace(_trace)
    try:
        exec(compiled, globals_dict)
    finally:
        sys.settrace(None)

    return trace_events
