from fastapi import APIRouter

from backend.models.schemas import AnalyzeRequest, AnalyzeResponse
from backend.services.ai_reasoning_engine import generate_reasoning
from backend.services.divergence_engine import compute_divergence
from backend.services.execution_engine import trace_execution
from backend.services.graph_engine import build_graph
from backend.services.intent_engine import model_intent
from backend.services.parser_service import parse_code


analyze_router = APIRouter()


@analyze_router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    """Run the full ACRE/EIME pipeline and return structured insights."""
    try:
        code = request.code

        ir_result = parse_code(code)
        if "error" in ir_result:
            execution_result = {"error": "Parsing failed; execution skipped."}
        else:
            try:
                execution_result = trace_execution(code)
            except Exception as exc:  # pragma: no cover - defensive
                execution_result = {"error": str(exc)}

        if "error" in ir_result:
            intent_result = {"error": "Intent modeling skipped after parsing failure."}
        else:
            try:
                intent_result = model_intent(code, ir_result)
            except Exception as exc:  # pragma: no cover - defensive
                intent_result = {"error": str(exc)}

        divergence_result = {}
        if (
            isinstance(execution_result, dict)
            and not execution_result.get("error")
            and isinstance(intent_result, dict)
            and not intent_result.get("error")
        ):
            try:
                divergence_result = compute_divergence(
                    execution_result.get("trace", []), intent_result
                )
            except Exception as exc:  # pragma: no cover - defensive
                divergence_result = {
                    "first_divergence": "",
                    "score": 0.0,
                    "severity": "UNKNOWN",
                    "causal_chain": [],
                    "error": str(exc),
                }
        else:
            divergence_result = {
                "first_divergence": "",
                "score": 0.0,
                "severity": "UNKNOWN",
                "causal_chain": [],
                "error": "Divergence unavailable because prior step failed.",
            }

        graph_result = {}
        if (
            isinstance(execution_result, dict)
            and not execution_result.get("error")
            and isinstance(intent_result, dict)
            and not intent_result.get("error")
            and isinstance(divergence_result, dict)
            and not divergence_result.get("error")
        ):
            graph_result = build_graph(
                execution_result.get("trace", []),
                intent_result.get("intent_trace", []),
                divergence_result.get("mismatches", []),
            )
        else:
            graph_result = {
                "nodes": [],
                "edges": [],
                "first_divergence": "",
                "error": "Graph unavailable due to upstream failure.",
            }

        reasoning_result = {}
        if (
            isinstance(intent_result, dict)
            and not intent_result.get("error")
            and isinstance(divergence_result, dict)
            and not divergence_result.get("error")
        ):
            reasoning_result = generate_reasoning(code, intent_result, divergence_result)
        else:
            reasoning_result = {"error": "Reasoning unavailable due to upstream failure."}

        metrics = {
            "intent_confidence": float(intent_result.get("confidence", 0.0))
            if isinstance(intent_result, dict)
            else 0.0,
            "alignment": 0.0,
            "divergence_score": 0.0,
        }

        if isinstance(divergence_result, dict) and not divergence_result.get("error"):
            total_steps = divergence_result.get("total_steps", 1)
            aligned = divergence_result.get("aligned_steps", 0)
            metrics["alignment"] = aligned / max(total_steps, 1)
            metrics["divergence_score"] = divergence_result.get("score", 0.0)

        if isinstance(execution_result, dict) and not execution_result.get("error"):
            execution_trace_field = execution_result.get("trace", [])
        else:
            execution_trace_field = []

        intent_field = intent_result if not intent_result.get("error") else {"error": intent_result.get("error")}
        divergence_field = divergence_result if not divergence_result.get("error") else {"error": divergence_result.get("error")}
        graph_field = graph_result if "nodes" in graph_result else {"error": graph_result.get("error")}
        reasoning_field = (
            reasoning_result
            if reasoning_result and not reasoning_result.get("error")
            else {"error": reasoning_result.get("error")}
        )

        response = AnalyzeResponse(
            execution_trace=execution_trace_field,
            intent_result=intent_field,
            divergence=divergence_field,
            graph=graph_field,
            reasoning=reasoning_field,
            metrics=metrics,
        )

        return response

    except Exception:
        import traceback

        traceback.print_exc()
        raise

