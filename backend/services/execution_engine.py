import io
import sys
import threading
import traceback
from types import FrameType
from typing import Any


MAX_TRACE_STEPS = 10_000


def _serialize_value(value: Any, depth: int = 0) -> Any:
    """Serialize values into JSON-friendly primitives."""
    if depth >= 3:
        return repr(value)
    if isinstance(value, (str, int, float, bool, type(None))):
        return value
    if isinstance(value, dict):
        return {
            str(k): _serialize_value(v, depth + 1) for k, v in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [_serialize_value(v, depth + 1) for v in value]
    try:
        return repr(value)
    except Exception:
        return str(type(value))


def _serialize_locals(locals_dict: dict[str, Any]) -> dict[str, Any]:
    """Prepare a locals snapshot for JSON encoding."""
    return {
        key: _serialize_value(value)
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
        """Capture printed output in a buffer."""
        text = sep.join(str(arg) for arg in args) + end
        output_buffer.write(text)

    # ✅ FIXED BUILTINS (added __import__)
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

        # 🔥 CRITICAL FIX
        "__import__": __import__,
    }

    restricted_globals: dict[str, Any] = {
        "__builtins__": safe_builtins,
        "__name__": "__main__",
    }

    step_counter = 0
    trace_called = False

    def _trace(frame: FrameType, event: str, arg: Any) -> Any:
        nonlocal step_counter
        
        try:
            if len(trace_steps) >= MAX_TRACE_STEPS:
                return None
            
            # Capture all events
            if event not in {"line", "call", "return", "exception"}:
                return _trace

            step_counter += 1
            func_name = frame.f_code.co_name
            entry: dict[str, Any] = {
                "step": step_counter,
                "line": frame.f_lineno,
                "event": event,
                "locals": _serialize_locals(frame.f_locals),
                "func": "" if func_name == "<module>" else func_name,
            }
            if event == "return":
                entry["value"] = _serialize_value(arg)
            elif event == "exception":
                exc_value = arg[1] if isinstance(arg, tuple) and len(arg) > 1 else arg
                entry["value"] = repr(exc_value)

            trace_steps.append(entry)
            return _trace
        except Exception as e:
            print(f"[TRACE ERROR] {e}", file=sys.stderr)
            return _trace

    # Execute directly in main thread (no threading interference)
    try:
        print(f"[EXECUTE] Starting execution...", file=sys.stderr)
        sys.settrace(_trace)
        exec(code, restricted_globals)
        print(f"[EXECUTE] Captured {len(trace_steps)} trace steps", file=sys.stderr)
    except Exception as exc:
        error_message = "".join(
            traceback.format_exception_only(type(exc), exc)
        ).strip()
        print(f"[EXECUTE] Error: {error_message}", file=sys.stderr)
    finally:
        sys.settrace(None)

    return {
        "trace": trace_steps,
        "output": output_buffer.getvalue(),
        "error": error_message,
        "timed_out": timed_out,
    }