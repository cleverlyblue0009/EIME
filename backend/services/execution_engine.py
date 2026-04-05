import io
import sys
import traceback
from types import FrameType
from typing import Any

MAX_TRACE_STEPS = 10_000
USER_CODE_FILENAME = "<intent_modeling_code>"


def serialize_value(value: Any, depth: int = 0) -> Any:
    """Serialize values into JSON-friendly primitives."""
    if depth >= 3:
        return repr(value)
    if isinstance(value, (str, int, float, bool, type(None))):
        return value
    if isinstance(value, dict):
        return {str(k): serialize_value(v, depth + 1) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [serialize_value(v, depth + 1) for v in value]
    try:
        return repr(value)
    except Exception:
        return str(type(value))


def serialize_locals(locals_dict: dict[str, Any]) -> dict[str, Any]:
    """Prepare a locals snapshot for JSON encoding."""
    return {
        key: serialize_value(value)
        for key, value in locals_dict.items()
        if not key.startswith("__")
    }


def trace_execution(code: str, timeout_seconds: float = 5.0) -> dict:
    """Execute code under a tracer and record per-line execution details."""
    output_buffer = io.StringIO()
    trace_steps: list[dict[str, Any]] = []
    error_message: str | None = None
    timed_out = False

    def _print_proxy(*args: Any, sep: str = " ", end: str = "\n", **kwargs: Any) -> None:
        text = sep.join(str(arg) for arg in args) + end
        output_buffer.write(text)

    safe_builtins = {
        "print": _print_proxy,
        "range": range,
        "len": len,
        "sum": sum,
        "max": max,
        "min": min,
        "abs": abs,
        "round": round,
        "enumerate": enumerate,
        "zip": zip,
        "list": list,
        "dict": dict,
        "set": set,
        "tuple": tuple,
        "sorted": sorted,
        "map": map,
        "filter": filter,
        "int": int,
        "float": float,
        "str": str,
        "bool": bool,
        "any": any,
        "all": all,
        "Exception": Exception,
        "ValueError": ValueError,
        "TypeError": TypeError,
        "__import__": __import__,
    }

    restricted_globals: dict[str, Any] = {
        "__builtins__": safe_builtins,
        "__name__": "__main__",
    }

    step_counter = 0
    recorded_returns: set[int] = set()
    call_stack: list[int] = []

    def _trace(frame: FrameType, event: str, arg: Any) -> Any:
        nonlocal step_counter

        try:
            if frame.f_code.co_filename != USER_CODE_FILENAME:
                return _trace

            if len(trace_steps) >= MAX_TRACE_STEPS:
                return None

            if event not in {"line", "call", "return", "exception"}:
                return _trace

            frame_id = id(frame)
            func_name = frame.f_code.co_name

            if event == "call":
                call_stack.append(frame_id)
            elif event in {"return", "exception"}:
                if call_stack and call_stack[-1] == frame_id:
                    call_stack.pop()

            if event == "return" and frame_id in recorded_returns:
                return _trace

            step_counter += 1

            entry: dict[str, Any] = {
                "step": step_counter,
                "line": frame.f_lineno,
                "event": event,
                "locals": serialize_locals(frame.f_locals),
                "func": "" if func_name == "<module>" else func_name,
                "frame_id": frame_id,
                "stack_depth": len(call_stack),
            }
            if event == "return":
                entry["value"] = serialize_value(arg)
                recorded_returns.add(frame_id)
            elif event == "exception":
                exc_value = arg[1] if isinstance(arg, tuple) and len(arg) > 1 else arg
                entry["value"] = repr(exc_value)

            trace_steps.append(entry)
            return _trace
        except Exception as exc:
            print(f"[TRACE ERROR] {exc}", file=sys.stderr)
            return _trace

    try:
        compiled = compile(code, USER_CODE_FILENAME, "exec")
        sys.settrace(_trace)
        exec(compiled, restricted_globals)
    except Exception as exc:
        error_message = "".join(traceback.format_exception_only(type(exc), exc)).strip()
    finally:
        sys.settrace(None)

    return {
        "trace": trace_steps,
        "output": output_buffer.getvalue(),
        "error": error_message,
        "timed_out": timed_out,
        "filename": USER_CODE_FILENAME,
    }
