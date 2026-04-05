import ast

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from backend.models.schemas import AnalyzeRequest, AnalyzeResponse, SimulateRequest
from backend.routes.analyze import analyze as run_analyze


simulate_router = APIRouter()


class _LoopBoundTransformer(ast.NodeTransformer):
    def __init__(self, new_bound: int) -> None:
        self.new_bound = new_bound
        self.replaced = False

    def visit_For(self, node: ast.For) -> ast.AST:
        if self.replaced:
            return self.generic_visit(node)

        iterator = node.iter
        if isinstance(iterator, ast.Call) and isinstance(iterator.func, ast.Name):
            if iterator.func.id == "range" and iterator.args:
                iterator.args[-1] = ast.copy_location(
                    ast.Constant(value=self.new_bound),
                    iterator.args[-1],
                )
                self.replaced = True

        return self.generic_visit(node)


def _apply_overrides(code: str, overrides: dict | None) -> str:
    if not overrides:
        return code

    variables = overrides.get("variables") if isinstance(overrides, dict) else {}
    condition = overrides.get("condition") if isinstance(overrides, dict) else None
    condition_line = overrides.get("conditionLine") if isinstance(overrides, dict) else None
    if condition_line is None and isinstance(overrides, dict):
        condition_line = overrides.get("condition_line")

    lines = code.split("\n")
    start_marker = "# --- EIME SIM OVERRIDES START ---"
    end_marker = "# --- EIME SIM OVERRIDES END ---"

    if start_marker in lines and end_marker in lines:
        start_idx = lines.index(start_marker)
        end_idx = lines.index(end_marker)
        if end_idx > start_idx:
            del lines[start_idx : end_idx + 1]

    if condition and condition_line:
        index = condition_line - 1
        if 0 <= index < len(lines):
            line = lines[index]
            stripped = line.lstrip()
            indent = line[: len(line) - len(stripped)]
            if stripped.startswith("if "):
                after_if = stripped[len("if ") :]
                suffix = after_if.split(":", 1)[1] if ":" in after_if else ""
                lines[index] = f"{indent}if {condition}:{suffix}"
            if stripped.startswith("while "):
                after_while = stripped[len("while ") :]
                suffix = after_while.split(":", 1)[1] if ":" in after_while else ""
                lines[index] = f"{indent}while {condition}:{suffix}"

    override_lines = []
    if isinstance(variables, dict):
        for key, value in variables.items():
            override_lines.append(f"{key} = {value}")

    if override_lines:
        lines = [start_marker, *override_lines, end_marker, *lines]

    return "\n".join(lines)


@simulate_router.post("/simulate", response_model=AnalyzeResponse)
async def simulate(request: SimulateRequest):
    try:
        patched_code = _apply_overrides(request.code, request.overrides)
        tree = ast.parse(patched_code)
    except SyntaxError as exc:
        raise HTTPException(status_code=422, detail=f"Syntax error: {exc}")

    transformer = _LoopBoundTransformer(request.input_size)
    tree = transformer.visit(tree)
    ast.fix_missing_locations(tree)

    if not transformer.replaced:
        # For code without numeric-range loops, simulation can't alter bound.
        # Fallback to normal analysis instead of hard 422.
        analyze_request = AnalyzeRequest(code=request.code, language="python")
        return await run_analyze(analyze_request)

    try:
        modified_code = ast.unparse(tree)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AST unparse failed: {e}")

    analyze_request = AnalyzeRequest(code=modified_code, language="python")

    return await run_analyze(analyze_request)
