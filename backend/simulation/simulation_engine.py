from __future__ import annotations

import ast
import re
from typing import Any, Dict, List

from backend.api.models import AnalysisResponse, SimulationPatch
from backend.pipeline import run_analysis


def _coerce_literal(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text:
        return value
    try:
        return ast.literal_eval(text)
    except Exception:
        return value


def _indent_of(line: str) -> str:
    match = re.match(r"\s*", line)
    return match.group(0) if match else ""


def _insert_before_line(lines: List[str], lineno: int, statement: str) -> str:
    idx = max(min(lineno - 1, len(lines)), 0)
    indent = _indent_of(lines[idx]) if 0 <= idx < len(lines) else ""
    lines.insert(idx, f"{indent}{statement}")
    return "\n".join(lines)


def apply_patch_to_code(code: str, patch: SimulationPatch) -> str:
    if patch.patch_type == "code_edit" and patch.updated_code:
        return patch.updated_code

    if patch.patch_type == "variable_override" and patch.target_variable:
        value_literal = repr(_coerce_literal(patch.new_value))
        statement = f"{patch.target_variable} = {value_literal}"
        lines = code.splitlines()
        if patch.target_line:
            return _insert_before_line(lines, patch.target_line, statement)
        return statement + "\n" + code

    if patch.patch_type == "loop_bound_override" and patch.target_line:
        lines = code.splitlines()
        idx = patch.target_line - 1
        if 0 <= idx < len(lines):
            line = lines[idx]
            if "range" in line:
                new_bound = _coerce_literal(patch.new_value)
                lines[idx] = re.sub(r"range\(([^)]*)\)", f"range({new_bound})", line)
            else:
                override_stmt = f"__ime_loop_bound_override = {repr(_coerce_literal(patch.new_value))}"
                return _insert_before_line(lines, patch.target_line, override_stmt)
        return "\n".join(lines)

    if patch.patch_type == "condition_override" and patch.target_line:
        lines = code.splitlines()
        idx = patch.target_line - 1
        if 0 <= idx < len(lines):
            line = lines[idx]
            indent = _indent_of(line)
            stripped = line.strip()
            new_condition = str(patch.new_value).strip()
            if stripped.startswith("if ") and stripped.endswith(":"):
                lines[idx] = f"{indent}if {new_condition}:"
            elif stripped.startswith("while ") and stripped.endswith(":"):
                lines[idx] = f"{indent}while {new_condition}:"
        return "\n".join(lines)

    return code


class SimulationEngine:
    def __init__(self) -> None:
        self.cache: Dict[str, Dict[str, Any]] = {}

    def apply_patch(self, analysis_id: str, patch: SimulationPatch, cached_analysis: AnalysisResponse) -> AnalysisResponse:
        code = cached_analysis.graph.get("source") if isinstance(cached_analysis.graph, dict) else None
        if not code:
            return cached_analysis
        new_code = apply_patch_to_code(code, patch)
        return run_analysis(new_code)
