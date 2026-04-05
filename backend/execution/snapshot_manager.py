from __future__ import annotations

from collections import deque
from copy import deepcopy
from types import BuiltinFunctionType, FunctionType, MethodType, ModuleType
from typing import Any, Dict, Iterable

_MAX_DEPTH = 4
_MAX_ITEMS = 64
_SKIP = object()
_INTERNAL_VALUE_TYPES = (type, ModuleType, FunctionType, BuiltinFunctionType, MethodType)


def _should_skip_mapping_key(key: Any) -> bool:
    return isinstance(key, str) and key.startswith("__")


def _is_internal_value(value: Any) -> bool:
    return isinstance(value, _INTERNAL_VALUE_TYPES) or callable(value)


def _truncate_items(items: Iterable[Any]) -> list[Any]:
    collected: list[Any] = []
    for index, item in enumerate(items):
        if index >= _MAX_ITEMS:
            break
        collected.append(item)
    return collected


def _clean_object_attributes(value: Any) -> Dict[str, Any]:
    try:
        raw_items = vars(value).items()
    except Exception:
        return {}
    return {
        key: attr
        for key, attr in raw_items
        if not key.startswith("__") and not _is_internal_value(attr)
    }


def serialize_value(value: Any, depth: int = 0, seen: set[int] | None = None) -> Any:
    if seen is None:
        seen = set()

    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    if _is_internal_value(value):
        return _SKIP

    value_id = id(value)
    if value_id in seen:
        return "<cycle>"
    if depth >= _MAX_DEPTH:
        return "<truncated>"

    next_seen = set(seen)
    next_seen.add(value_id)

    if isinstance(value, dict):
        cleaned: Dict[Any, Any] = {}
        for key, item in _truncate_items(value.items()):
            if _should_skip_mapping_key(key):
                continue
            serialized = serialize_value(item, depth + 1, next_seen)
            if serialized is _SKIP:
                continue
            cleaned[key] = serialized
        return cleaned

    if isinstance(value, (list, tuple, deque)):
        result = []
        for item in _truncate_items(value):
            serialized = serialize_value(item, depth + 1, next_seen)
            if serialized is _SKIP:
                continue
            result.append(serialized)
        return result

    if isinstance(value, (set, frozenset)):
        result = []
        for item in _truncate_items(sorted(value, key=lambda item: repr(item))):
            serialized = serialize_value(item, depth + 1, next_seen)
            if serialized is _SKIP:
                continue
            result.append(serialized)
        return result

    attributes = _clean_object_attributes(value)
    if attributes:
        cleaned = {}
        for key, item in attributes.items():
            serialized = serialize_value(item, depth + 1, next_seen)
            if serialized is _SKIP:
                continue
            cleaned[key] = serialized
        if cleaned:
            return cleaned

    return _SKIP


def serialize_locals(locals_dict: Dict[str, Any]) -> Dict[str, Any]:
    cleaned: Dict[str, Any] = {}
    for key, value in locals_dict.items():
        if key.startswith("__") or _is_internal_value(value):
            continue
        serialized = serialize_value(value)
        if serialized is _SKIP:
            continue
        cleaned[key] = serialized
    return cleaned


def clone_snapshot(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    return deepcopy(snapshot)
