from __future__ import annotations

import uuid
from typing import Any, Dict, List, Literal, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class LineRef(BaseModel):
    lineno: int
    col_offset: Optional[int] = None
    end_lineno: Optional[int] = None


class AnalysisRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    code: str
    stdin_input: Optional[str] = ""
    simulation_params: Dict[str, Any] = Field(default_factory=dict)
    gemini_api_key: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("gemini_api_key", "llm_api_key"),
        serialization_alias="gemini_api_key",
    )


class TraceEvent(BaseModel):
    event_id: int
    timestamp_ns: int
    event_type: Literal["call", "line", "return", "exception"]
    lineno: int
    function_name: str
    frame_id: Optional[int] = None
    locals_snapshot: Dict[str, Any] = Field(default_factory=dict)
    call_stack_depth: int
    loop_iteration: Optional[int] = None
    return_value: Optional[Any] = None
    exception_info: Optional[str] = None


class LoopSummary(BaseModel):
    loop_id: str
    header_line: int
    iteration_count: int
    loop_variable: Optional[str]
    exit_reason: str
    variables_mutated: List[str]
    per_iteration_snapshots: List[Dict[str, Any]]
    iteration_step_ids: List[int] = Field(default_factory=list)
    function_context: Optional[str] = None


class FunctionCall(BaseModel):
    call_id: str
    function_name: str
    call_site_line: int
    arguments: Dict[str, Any] = Field(default_factory=dict)
    return_value: Optional[Any] = None
    child_calls: List[str]
    is_recursive: bool
    recursion_depth: int


class ExecutionStep(BaseModel):
    step_id: int
    lineno: int
    description: str
    variable_deltas: Dict[str, Dict[str, Any]]
    context: Literal["MAIN", "LOOP", "FUNCTION", "RECURSION"]
    loop_iteration: Optional[int] = None
    function_name: Optional[str] = None
    parent_step_id: Optional[int] = None
    event_type: Optional[str] = None
    code_line: Optional[str] = None
    variable_snapshot: Dict[str, Any] = Field(default_factory=dict)
    operation: Optional[str] = None
    explanation: Optional[str] = None
    algorithm_role: Optional[str] = None
    reads: List[str] = Field(default_factory=list)
    read_accesses: List[str] = Field(default_factory=list)
    writes: List[str] = Field(default_factory=list)
    write_accesses: List[str] = Field(default_factory=list)
    code_snippet: Optional[str] = None
    variables: Dict[str, Any] = Field(default_factory=dict)
    operation_type: Optional[str] = None
    iteration_index: Optional[int] = None
    function_context: Optional[str] = None
    data_dependencies: List[str] = Field(default_factory=list)
    focus_variables: Dict[str, Any] = Field(default_factory=dict)
    group_id: Optional[str] = None
    timestamp_ns: Optional[int] = None
    scope_depth: int = 0
    scope_event: Optional[Literal["enter", "step", "exit", "exception"]] = None
    scope_label: Optional[str] = None


class NormalizedTrace(BaseModel):
    steps: List[ExecutionStep]
    loop_summaries: List[LoopSummary]
    function_calls: List[FunctionCall]
    path_taken: List[str]
    final_state: Dict[str, Any] = Field(default_factory=dict)
    total_steps: int
    max_recursion_depth: int


class VariableRole(BaseModel):
    variable_name: str
    role: Literal[
        "ACCUMULATOR",
        "WINDOW_START",
        "WINDOW_END",
        "MEMO_TABLE",
        "VISITED_SET",
        "RESULT_CANDIDATE",
        "LOOP_COUNTER",
        "POINTER_LEFT",
        "POINTER_RIGHT",
        "FAST_POINTER",
        "SLOW_POINTER",
        "STACK_DS",
        "QUEUE_DS",
        "HEAP_DS",
        "PARENT_MAP",
        "DISTANCE_MAP",
        "IN_DEGREE",
        "DP_TABLE",
        "FREQUENCY_MAP",
        "GRAPH_ADJ",
        "MONOTONIC_STACK",
        "MONOTONIC_QUEUE",
        "TRIE_NODE",
        "UNION_FIND_PARENT",
        "BIT_MASK",
        "LEFT_BOUND",
        "RIGHT_BOUND",
        "MID_POINTER",
        "COMPARATOR",
        "UNKNOWN",
    ]
    confidence: float
    evidence: str


class Invariant(BaseModel):
    description: str
    formal_expression: Optional[str]
    criticality: Literal["HIGH", "MEDIUM", "LOW"]
    holds_at: List[str]


class AlgorithmPhase(BaseModel):
    phase_name: str
    start_line: int
    end_line: int
    description: str
    expected_complexity: str


class IntentModel(BaseModel):
    inferred_algorithm: str
    algorithm_variant: str
    confidence: float
    programmer_goal: str
    invariants: List[Invariant]
    expected_variable_roles: Dict[str, VariableRole]
    algorithm_phase_sequence: List[AlgorithmPhase]
    known_pitfalls: List[str]
    expected_time_complexity: str
    expected_space_complexity: str
    source: Literal["STRUCTURAL", "LLM", "HYBRID"]
    llm_advisory: Dict[str, Any] = Field(default_factory=dict)


class Checkpoint(BaseModel):
    program_point: LineRef
    condition: str
    expected_values: Dict[str, Any]
    criticality: Literal["MUST", "SHOULD", "MAY"]


class ExpectationModel(BaseModel):
    expected_loop_counts: Dict[str, int]
    expected_loop_count_formulas: Dict[str, str]
    expected_variable_final_values: Dict[str, Any]
    expected_output: Any
    critical_checkpoints: List[Checkpoint]
    expected_recursion_depth: Optional[int]
    expected_memo_table_size: Optional[int]


class InvariantObservation(BaseModel):
    invariant: str
    expected_condition: str
    observed_condition: str
    violation: bool
    related_steps: List[int] = Field(default_factory=list)
    line_numbers: List[int] = Field(default_factory=list)
    confidence: float = 0.0
    evidence: Dict[str, Any] = Field(default_factory=dict)


class IntentStep(BaseModel):
    intent_step_id: str
    label: str
    description: str
    phase_type: Literal["goal", "phase", "invariant"]
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    invariants: List[str] = Field(default_factory=list)
    algorithm_role: Optional[str] = None
    confidence: float = 0.0


class AlignmentEntry(BaseModel):
    execution_step_id: int
    intent_step_id: str
    relation: Literal["supports", "violates", "context", "unknown"]
    score: float
    rationale: str
    line_number: Optional[int] = None
    function_context: Optional[str] = None


class CausalStep(BaseModel):
    step_index: int
    description: str
    lineno: int
    variable_state: Dict[str, Any]
    why_this_matters: str


class Divergence(BaseModel):
    divergence_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: Literal[
        "LOOP_BOUND_ERROR",
        "LOOP_MISSING_LAST_ITERATION",
        "WINDOW_INCOMPLETENESS",
        "BASE_CASE_MISSING",
        "INVARIANT_VIOLATION",
        "OFF_BY_ONE",
        "CONDITION_SENSE_INVERSION",
        "MISSING_STATE_UPDATE",
        "PREMATURE_TERMINATION",
        "WRONG_ACCUMULATION",
        "HEAP_PROPERTY_VIOLATION",
        "HEAP_INDEX_ERROR",
        "DP_TRANSITION_ERROR",
        "DP_STATE_INCONSISTENCY",
        "POINTER_DESYNC",
        "MISSING_EDGE_CASE",
        "WRONG_POINTER_ADVANCE",
        "MEMOIZATION_MISS",
        "WRONG_VISITED_CHECK",
        "BFS_VISITED_LATE",
        "BACKTRACK_RESTORE_MISSING",
        "WRONG_SORT_KEY",
        "WRONG_MERGE_CONDITION",
        "MONOTONIC_VIOLATION",
        "WRONG_RELAXATION",
        "WRONG_UNION_ORDER",
        "TRIE_TERMINATION_ERROR",
        "WRONG_BIT_OPERATION",
        "WRONG_HASH_FUNCTION",
        "MISSING_NULL_CHECK",
        "WRONG_DIRECTION",
        "EARLY_RETURN",
        "WRONG_COMPARATOR",
        "MISSING_DECREASE_KEY",
        "WRONG_WINDOW_UPDATE",
        "RESULT_NOT_UPDATED_IN_LOOP",
        "MISSING_INITIAL_WINDOW",
        "OFF_BY_ONE_BOUND",
        "WRONG_BASE_CASE_VALUE",
        "WRONG_RECURSIVE_RETURN",
        "RESULT_APPENDS_REFERENCE",
        "WRONG_PRUNING",
        "WRONG_RETURN_VALUE",
        "WRONG_HEAP_SIZE_MAINTENANCE",
        "WRONG_INDEX_ACCESS",
        "WRONG_STATE_SELECTION",
        "WRONG_CONDITION_CHECK",
        "SEMANTIC_MISMATCH",
    ]
    severity: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    causal_chain: List[CausalStep]
    first_occurrence_line: int
    symptom_line: int
    expected_behavior: str
    actual_behavior: str
    affected_variables: List[str]
    affected_lines: List[int]
    algorithm_context: str
    fix_suggestion: str
    expected_state: Optional[Any] = None
    actual_state: Optional[Any] = None
    missing_state: Optional[Any] = None
    extra_state: Optional[Any] = None
    divergence_point: Optional[str] = None
    explanation: Optional[str] = None
    root_cause: Optional[str] = None
    evidence: Dict[str, Any] = Field(default_factory=dict)


class NodeDetail(BaseModel):
    full_description: str
    variable_snapshot: Dict[str, Any]
    code_ref: Optional[LineRef]
    role_in_algorithm: str
    why_matters: str
    invariants_checked: List[str]
    step: Optional[int] = None
    operation: Optional[str] = None
    code_line: Optional[str] = None
    expected_state: Optional[Any] = None
    actual_state: Optional[Any] = None
    missing_state: Optional[Any] = None
    extra_state: Optional[Any] = None
    causal_chain: List[Dict[str, Any]] = Field(default_factory=list)
    story_phase: Optional[str] = None
    iteration_index: Optional[int] = None
    function_context: Optional[str] = None
    preview_variables: Dict[str, Any] = Field(default_factory=dict)
    read_variables: List[str] = Field(default_factory=list)
    write_variables: List[str] = Field(default_factory=list)
    hover_summary: Optional[str] = None
    group_kind: Optional[str] = None
    is_divergence_path: bool = False
    line_number: Optional[int] = None
    code_snippet: Optional[str] = None
    variables: Dict[str, Any] = Field(default_factory=dict)
    operation_type: Optional[str] = None
    zoom_levels: List[Literal["function", "loop", "step"]] = Field(default_factory=list)
    member_step_ids: List[int] = Field(default_factory=list)
    group_id: Optional[str] = None
    editable_fields: List[str] = Field(default_factory=list)
    data_dependencies: List[str] = Field(default_factory=list)
    controls: Dict[str, Any] = Field(default_factory=dict)
    variable_deltas: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    timestamp_ns: Optional[int] = None
    parent_step_id: Optional[int] = None
    scope_depth: int = 0
    scope_event: Optional[str] = None
    alignment_targets: List[str] = Field(default_factory=list)


class GraphNode(BaseModel):
    id: str
    type: Literal[
        "execution",
        "intent",
        "divergence",
        "function_entry",
        "function_exit",
        "loop_header",
        "loop_iteration",
        "loop_exit",
        "data",
        "merge_point",
        "branch_true",
        "branch_false",
        "recursion_call",
        "recursion_base",
    ]
    label: str
    detail: NodeDetail
    position: Dict[str, float]
    visual_tier: int
    collapsed: bool
    cluster_id: Optional[str]


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    type: Literal[
        "control_flow",
        "data_flow",
        "dependency",
        "mutation",
        "intent_alignment",
        "intent_violation",
        "call",
        "return",
        "loop_back",
        "loop_exit",
        "branch_true",
        "branch_false",
        "recursive_call",
        "memoized_return",
    ]
    label: Optional[str]
    animated: bool
    weight: float
    variables: List[str] = Field(default_factory=list)


class CognitiveGraph(BaseModel):
    nodes: List[GraphNode] = Field(default_factory=list)
    edges: List[GraphEdge] = Field(default_factory=list)
    meta: Dict[str, Any] = Field(default_factory=dict)
    source: Optional[str] = None
    first_divergence: Optional[str] = None


class ReasoningOutput(BaseModel):
    executive_summary: str
    intended_behavior: str
    actual_behavior: str
    divergence_explanation: str
    root_cause: str
    fix_suggestion: str
    algorithm_explanation: str
    confidence: float
    llm_summary: Optional[str] = None
    llm_algorithm_guess: Optional[str] = None
    deeper_bug_hypotheses: List[str] = Field(default_factory=list)
    deterministic_boundary: str = (
        "Execution, trace construction, divergence detection, and simulation are deterministic. "
        "Gemini reasoning is the mandatory second pass for semantic explanation, but it never replaces "
        "deterministic execution correctness."
    )


class Metrics(BaseModel):
    intent_confidence: float
    alignment_score: float
    divergence_score: float
    execution_steps: int
    divergence_count: int
    algorithm_detected: str
    algorithm_variant: str
    execution_alignment_score: float = 0.0
    divergence_severity_score: float = 0.0
    invariant_coverage_score: float = 0.0
    invariant_violations: int = 0
    aligned_steps: int = 0
    data_flow_edges: int = 0
    intent_step_count: int = 0


class AnalysisResponse(BaseModel):
    analysis_id: str
    normalized_trace: NormalizedTrace
    intent_model: IntentModel
    expectation_model: ExpectationModel
    divergences: List[Divergence]
    graph: Dict[str, Any]
    execution_graph: Dict[str, Any] = Field(default_factory=dict)
    intent_graph: Dict[str, Any] = Field(default_factory=dict)
    data_flow_graph: Dict[str, Any] = Field(default_factory=dict)
    alignment_map: List[Dict[str, Any]] = Field(default_factory=list)
    invariant_report: List[Dict[str, Any]] = Field(default_factory=list)
    divergence_report: List[Dict[str, Any]] = Field(default_factory=list)
    reasoning: ReasoningOutput
    metrics: Metrics
    execution_trace: List[Dict[str, Any]] = Field(default_factory=list)
    intent: Dict[str, Any] = Field(default_factory=dict)
    divergence: Dict[str, Any] = Field(default_factory=dict)


class SimulationPatch(BaseModel):
    analysis_id: str
    patch_type: Literal["variable_override", "loop_bound_override", "condition_override", "code_edit"]
    target_line: Optional[int] = None
    target_variable: Optional[str] = None
    target_step_id: Optional[int] = None
    target_group_id: Optional[str] = None
    new_value: Any = None
    updated_code: Optional[str] = None
