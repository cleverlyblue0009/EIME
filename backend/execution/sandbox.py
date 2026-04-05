from __future__ import annotations

import builtins
import io
from typing import Any, Dict, Tuple

from backend.execution.tracer import trace_code


def build_sandbox(stdin_input: str | None = None) -> Tuple[Dict[str, Any], io.StringIO]:
    output_buffer = io.StringIO()

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
        "next": next,
        "reversed": reversed,
        "slice": slice,
        "int": int,
        "float": float,
        "str": str,
        "bool": bool,
        "object": object,
        "isinstance": isinstance,
        "getattr": getattr,
        "setattr": setattr,
        "hasattr": hasattr,
        "super": super,
        "classmethod": classmethod,
        "staticmethod": staticmethod,
        "property": property,
        "any": any,
        "all": all,
        "Exception": Exception,
        "BaseException": BaseException,
        "ValueError": ValueError,
        "TypeError": TypeError,
        "AttributeError": AttributeError,
        "IndexError": IndexError,
        "KeyError": KeyError,
        "__build_class__": builtins.__build_class__,
        "__import__": __import__,
    }

    globals_dict: Dict[str, Any] = {
        "__builtins__": safe_builtins,
        "__name__": "__main__",
    }

    if stdin_input is not None:
        globals_dict["__stdin__"] = stdin_input

    return globals_dict, output_buffer


def execute_with_trace(code: str, stdin_input: str | None = None) -> Dict[str, Any]:
    globals_dict, output_buffer = build_sandbox(stdin_input)
    error: str | None = None
    trace_events = []

    try:
        trace_events = trace_code(code, globals_dict)
    except Exception as exc:  # pragma: no cover
        error = repr(exc)

    return {
        "trace": trace_events,
        "output": output_buffer.getvalue(),
        "error": error,
    }
