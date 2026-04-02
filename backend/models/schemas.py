from typing import Dict, List, Optional
from pydantic import BaseModel


class CodePayload(BaseModel):
    code: Optional[str] = None
    language: str = "python"
    scenario: Optional[str] = "base"
    input_size: Optional[int] = 50
    branch_behavior: Optional[str] = "deterministic"


class TraceStep(BaseModel):
    id: str
    label: str
    line: Optional[int]
    duration_ms: float
    type: str
    variables: Dict[str, str] = {}


class DivergenceDetail(BaseModel):
    first_divergence: str
    score: float
    severity: str
    causal_chain: List[str]
    highlights: List[str] = []


class GraphNode(BaseModel):
    id: str
    label: str
    type: str
    status: Optional[str] = None
    highlight: bool = False


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    type: str
    highlight: bool = False


class GraphPayload(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    first_divergence: str


class TraceResponse(BaseModel):
    execution_trace: List[TraceStep]
    intent_trace: List[TraceStep]
    divergence: DivergenceDetail
    graph: GraphPayload
    metrics: Dict[str, str]


class SimulationResponse(BaseModel):
    scenario: str
    status: str
    message: str
    metrics: Dict[str, str]
