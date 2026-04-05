from __future__ import annotations

import asyncio
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from backend.api.models import AnalysisRequest, AnalysisResponse, SimulationPatch
from backend.pipeline import run_analysis, run_analysis_staged
from backend.reasoning.llm_reasoner import GeminiConfigurationError, GeminiReasoningError
from backend.simulation.simulation_engine import apply_patch_to_code


router = APIRouter()
_analysis_context_cache: Dict[str, Dict[str, Any]] = {}


@router.post("/analyze", response_model=AnalysisResponse)
async def analyze(request: AnalysisRequest) -> AnalysisResponse:
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(
                run_analysis,
                request.code,
                request.stdin_input or "",
                request.gemini_api_key,
            ),
            timeout=30,
        )
    except asyncio.TimeoutError as exc:  # pragma: no cover
        raise HTTPException(status_code=504, detail="Analysis timed out") from exc
    except GeminiConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except GeminiReasoningError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    _analysis_context_cache[result.analysis_id] = {
        "code": request.code,
        "stdin_input": request.stdin_input or "",
        "gemini_api_key": request.gemini_api_key,
    }
    return result


@router.post("/simulate", response_model=AnalysisResponse)
async def simulate(patch: SimulationPatch) -> AnalysisResponse:
    code = patch.updated_code
    cached_context = _analysis_context_cache.get(patch.analysis_id, {})
    if not code:
        code = cached_context.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="Unknown analysis_id or missing code")

    patched_code = apply_patch_to_code(code, patch)
    result = await asyncio.to_thread(
        run_analysis,
        patched_code,
        cached_context.get("stdin_input", ""),
        cached_context.get("gemini_api_key"),
    )
    _analysis_context_cache[result.analysis_id] = {
        **cached_context,
        "code": patched_code,
    }
    return result


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "version": "2.0"}


async def stream_analysis(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        payload = await websocket.receive_json()
        code = payload.get("code", "")
        stdin_input = payload.get("stdin_input", "")
        gemini_api_key = payload.get("gemini_api_key") or payload.get("llm_api_key")
        for stage, data in run_analysis_staged(code, stdin_input, gemini_api_key):
            await websocket.send_json({"stage": stage, "data": data})
        final = run_analysis(code, stdin_input, gemini_api_key)
        _analysis_context_cache[final.analysis_id] = {
            "code": code,
            "stdin_input": stdin_input,
            "gemini_api_key": gemini_api_key,
        }
        await websocket.send_json({"stage": "complete", "data": final.model_dump()})
    except WebSocketDisconnect:
        return
    except GeminiConfigurationError as exc:
        await websocket.send_json({"stage": "error", "data": {"detail": str(exc)}})
    except GeminiReasoningError as exc:
        await websocket.send_json({"stage": "error", "data": {"detail": str(exc)}})
