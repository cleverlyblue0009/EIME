from typing import Literal
from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    code: str
    language: str = "python"

    model_config = {"extra": "ignore"}  # changed


class SimulateRequest(BaseModel):
    code: str
    input_size: int = Field(default=10, ge=1, le=1000)
    branch_mode: Literal["deterministic", "random"] = "deterministic"

    model_config = {"extra": "ignore"}  # changed


class AnalyzeResponse(BaseModel):
    execution_trace: list[dict]
    intent_result: dict
    divergence: dict
    graph: dict
    reasoning: dict
    metrics: dict[str, float]

    model_config = {"extra": "ignore"}  # changed