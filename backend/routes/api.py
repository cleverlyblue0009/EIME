from fastapi import APIRouter

from ..models.schemas import CodePayload, TraceResponse
from ..services.divergence_engine import build_graph_payload, detect_divergence
from ..services.execution_engine import run_execution
from ..services.intent_engine import build_intent
from ..services.simulation import run_simulation

router = APIRouter()


def _build_metrics(divergence_data: dict) -> dict:
    score = divergence_data.get("score", 0.4)
    confidence = divergence_data.get("confidence", score)
    alignment = "HIGH" if score >= 0.85 else "MEDIUM"
    return {
        "intent_confidence": f"{round(confidence * 100)}%",
        "alignment_score": alignment,
        "divergence_severity": divergence_data.get("severity", "MEDIUM"),
    }


@router.post("/analyze", response_model=TraceResponse)
async def analyze(payload: CodePayload):
    execution_trace = run_execution(payload.code or "")
    intent_trace = build_intent(payload.code or "")
    divergence_data = detect_divergence(execution_trace, intent_trace)
    graph_payload = build_graph_payload(execution_trace, intent_trace, divergence_data)
    metrics = _build_metrics(divergence_data)
    return TraceResponse(
        execution_trace=execution_trace,
        intent_trace=intent_trace,
        divergence=divergence_data,
        graph=graph_payload,
        metrics=metrics,
    )


@router.post("/intent")
async def intent(payload: CodePayload):
    intent_trace = build_intent(payload.code or "")
    return {
        "intent_trace": intent_trace,
        "metrics": {"intent_confidence": "100%", "alignment_score": "HIGH"},
    }


@router.post("/divergence")
async def divergence(payload: CodePayload):
    execution_trace = run_execution(payload.code or "")
    intent_trace = build_intent(payload.code or "")
    divergence_data = detect_divergence(execution_trace, intent_trace)
    return {"divergence": divergence_data}


@router.post("/simulate")
async def simulate(payload: CodePayload):
    result = run_simulation(
        payload.scenario or "base", payload.input_size or 50, payload.branch_behavior or "deterministic"
    )
    return result
