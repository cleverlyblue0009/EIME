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


@simulate_router.post("/simulate", response_model=AnalyzeResponse)
async def simulate(request: SimulateRequest):
    try:
        tree = ast.parse(request.code)
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