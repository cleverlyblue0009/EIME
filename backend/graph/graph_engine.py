from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional, Sequence

from backend.api.models import GraphEdge, GraphNode, LineRef, NodeDetail

MAX_DATA_EDGES_PER_STEP = 4


def build(normalized_trace, intent, divergences, parse_context) -> Dict[str, Any]:
    steps = list(getattr(normalized_trace, "steps", []) or [])
    source = parse_context.get("source", "") if parse_context else ""
    divergence_path_step_ids = _divergence_path_step_ids(steps, divergences)

    intent_node = _build_intent_node(intent)
    function_nodes = _build_function_nodes(normalized_trace.function_calls, steps, divergence_path_step_ids)
    loop_nodes = _build_loop_nodes(normalized_trace.loop_summaries, steps, divergence_path_step_ids)
    execution_nodes = [_build_execution_node(step, intent, step.step_id in divergence_path_step_ids) for step in steps]
    divergence_nodes = _build_divergence_nodes(divergences)

    nodes: List[GraphNode] = [intent_node]
    nodes.extend(function_nodes)
    nodes.extend(loop_nodes)
    nodes.extend(execution_nodes)
    nodes.extend(divergence_nodes)

    edges: List[GraphEdge] = []
    edges.extend(_build_story_edges(intent_node, function_nodes, loop_nodes, execution_nodes))
    edges.extend(_build_group_edges(function_nodes, loop_nodes, steps))
    edges.extend(_build_control_flow_edges(steps))
    edges.extend(_build_data_flow_edges(steps))
    edges.extend(_build_divergence_edges(execution_nodes, divergence_nodes, divergences))

    groups = _build_group_metadata(function_nodes, loop_nodes, steps)
    divergence_path_node_ids = {
        node.id
        for node in execution_nodes + function_nodes + loop_nodes + divergence_nodes
        if node.detail.is_divergence_path or node.type == "divergence"
    }

    return {
        "nodes": [node.model_dump() for node in nodes],
        "edges": [edge.model_dump() for edge in edges],
        "source": source,
        "first_divergence": divergences[0].type if divergences else None,
        "meta": {
            "levels": _build_level_metadata(intent_node, function_nodes, loop_nodes, execution_nodes, divergence_nodes),
            "clusters": _build_cluster_metadata(nodes),
            "groups": groups,
            "divergence_path_node_ids": sorted(divergence_path_node_ids),
            "story": _story_outline(intent, function_nodes, loop_nodes, divergences),
            "editable": {
                "variable_override": True,
                "loop_bound_override": True,
                "condition_override": True,
            },
        },
    }


def _build_intent_node(intent) -> GraphNode:
    advisory = getattr(intent, "llm_advisory", {}) or {}
    semantic_algorithm = advisory.get("algorithm_type") or intent.inferred_algorithm
    invariants = [item.description for item in getattr(intent, "invariants", [])]
    label = _algorithm_title(semantic_algorithm)
    description = advisory.get("human_explanation") or intent.programmer_goal or f"Implement {label} correctly."
    if advisory.get("algorithm_type") and advisory.get("algorithm_type") != intent.inferred_algorithm:
        description = (
            f"Structural pass classified this code as {_algorithm_title(intent.inferred_algorithm)}, "
            f"but Gemini's second pass reclassified it as {_algorithm_title(advisory['algorithm_type'])}. "
            f"{description}"
        )
    return GraphNode(
        id="intent_root",
        type="intent",
        label=label,
        detail=NodeDetail(
            full_description=description,
            variable_snapshot={},
            code_ref=None,
            role_in_algorithm=semantic_algorithm,
            why_matters="This is the semantic target used to judge whether the execution drifted.",
            invariants_checked=invariants,
            operation="intent",
            code_snippet=None,
            variables={},
            operation_type="intent",
            zoom_levels=["function", "loop", "step"],
            hover_summary=(
                f"Gemini intent: {label}"
                if advisory.get("algorithm_type")
                else f"Inferred intent: {label}"
            ),
            group_kind="intent",
            controls={"editable": False},
        ),
        position={"x": 0.0, "y": 0.0},
        visual_tier=0,
        collapsed=False,
        cluster_id="intent",
    )


def _build_function_nodes(function_calls, steps, divergence_path_step_ids: set[int]) -> List[GraphNode]:
    grouped: Dict[str, List[Any]] = defaultdict(list)
    first_step_by_name: Dict[str, Any] = {}
    for step in steps:
        if step.function_name and step.function_name != "<module>" and step.function_name not in first_step_by_name:
            first_step_by_name[step.function_name] = step
    for call in function_calls:
        if call.function_name and call.function_name != "<module>":
            grouped[call.function_name].append(call)

    nodes: List[GraphNode] = []
    for name, calls in sorted(grouped.items(), key=lambda item: getattr(first_step_by_name.get(item[0]), "step_id", 10**9)):
        first_step = first_step_by_name.get(name)
        preview = _focus_variables(calls[0].arguments if calls else {}, preferred=list((calls[0].arguments or {}).keys() if calls else []))
        member_step_ids = [step.step_id for step in steps if step.function_name == name]
        nodes.append(
            GraphNode(
                id=f"function_summary_{name}",
                type="function_entry",
                label=f"{name}()",
                detail=NodeDetail(
                    full_description=(
                        f"Function `{name}` owns a distinct execution chapter with {len(calls)} call(s). "
                        "Expand to inspect step-level state transitions inside the frame."
                    ),
                    variable_snapshot=calls[0].arguments if calls else {},
                    code_ref=LineRef(lineno=first_step.lineno if first_step else calls[0].call_site_line),
                    role_in_algorithm="function_summary",
                    why_matters="Grouping by function makes it easier to locate where semantic drift begins.",
                    invariants_checked=[],
                    operation="function_summary",
                    function_context=name,
                    preview_variables=preview,
                    hover_summary=f"{len(calls)} call(s) to {name}",
                    group_kind="function",
                    is_divergence_path=any(step_id in divergence_path_step_ids for step_id in member_step_ids),
                    line_number=first_step.lineno if first_step else None,
                    code_snippet=(first_step.code_snippet if first_step else None),
                    variables=calls[0].arguments if calls else {},
                    operation_type="function",
                    zoom_levels=["function", "loop", "step"],
                    member_step_ids=member_step_ids,
                    group_id=f"fn:{name}",
                    editable_fields=[],
                    controls={"editable": False, "expandable": True},
                ),
                position={"x": 0.0, "y": 0.0},
                visual_tier=0,
                collapsed=False,
                cluster_id=f"fn:{name}",
            )
        )
    return nodes


def _build_loop_nodes(loop_summaries, steps, divergence_path_step_ids: set[int]) -> List[GraphNode]:
    nodes: List[GraphNode] = []
    for loop in sorted(loop_summaries, key=lambda item: item.header_line):
        matching_steps = [step for step in steps if step.group_id == f"loop:{loop.header_line}"]
        preview = _focus_variables(loop.per_iteration_snapshots[0] if loop.per_iteration_snapshots else {})
        nodes.append(
            GraphNode(
                id=f"loop_summary_{loop.header_line}",
                type="loop_header",
                label=f"Loop L{loop.header_line} x{loop.iteration_count}",
                detail=NodeDetail(
                    full_description=(
                        f"The loop at line {loop.header_line} executes {loop.iteration_count} time(s). "
                        "This group can be expanded into step-by-step iteration state."
                    ),
                    variable_snapshot=loop.per_iteration_snapshots[0] if loop.per_iteration_snapshots else {},
                    code_ref=LineRef(lineno=loop.header_line),
                    role_in_algorithm="loop_summary",
                    why_matters="Loop groups collapse repetitive execution while preserving the exact iteration count and mutated state.",
                    invariants_checked=[],
                    operation="loop_summary",
                    iteration_index=loop.iteration_count,
                    function_context=loop.function_context,
                    preview_variables=preview,
                    hover_summary=f"{loop.iteration_count} iteration(s), mutates {', '.join(loop.variables_mutated[:3]) or 'tracked state'}",
                    group_kind="loop",
                    is_divergence_path=any(step.step_id in divergence_path_step_ids for step in matching_steps),
                    line_number=loop.header_line,
                    code_snippet=matching_steps[0].code_snippet if matching_steps else None,
                    variables=loop.per_iteration_snapshots[0] if loop.per_iteration_snapshots else {},
                    operation_type="loop",
                    zoom_levels=["loop", "step"],
                    member_step_ids=list(loop.iteration_step_ids),
                    group_id=f"loop:{loop.header_line}",
                    editable_fields=[],
                    controls={"editable": False, "expandable": True},
                ),
                position={"x": 0.0, "y": 0.0},
                visual_tier=0,
                collapsed=False,
                cluster_id=f"loop:{loop.header_line}",
            )
        )
    return nodes


def _build_execution_node(step, intent, divergence_path: bool) -> GraphNode:
    invariants = _relevant_invariants(intent, step)
    preview = dict(step.focus_variables or _focus_variables(step.variable_snapshot, list(step.write_accesses or []) + list(step.read_accesses or [])))
    detail = NodeDetail(
        full_description=_step_story(step),
        variable_snapshot=step.variable_snapshot,
        code_ref=LineRef(lineno=step.lineno),
        role_in_algorithm=step.algorithm_role or "execution_step",
        why_matters=_why_step_matters(step),
        invariants_checked=invariants,
        step=step.step_id,
        operation=step.operation,
        code_line=(step.code_line or "").strip(),
        story_phase="step",
        iteration_index=step.iteration_index,
        function_context=step.function_context,
        preview_variables=preview,
        read_variables=list(step.read_accesses or step.reads),
        write_variables=list(step.write_accesses or step.writes),
        hover_summary=_hover_summary_for_step(step, preview),
        group_kind="step",
        is_divergence_path=divergence_path,
        line_number=step.lineno,
        code_snippet=(step.code_snippet or step.code_line or "").strip(),
        variables=step.variables or step.variable_snapshot,
        operation_type=step.operation_type or step.operation,
        zoom_levels=["step"],
        member_step_ids=[step.step_id],
        group_id=step.group_id,
        editable_fields=sorted((step.variables or step.variable_snapshot).keys()),
        data_dependencies=list(step.data_dependencies or step.read_accesses),
        controls={
            "editable": True,
            "line_number": step.lineno,
            "step_id": step.step_id,
            "allow_variable_override": True,
            "allow_loop_bound_override": bool(step.group_id and step.group_id.startswith("loop:")),
            "allow_condition_override": (step.operation_type or step.operation) in {"branch", "loop_header"},
        },
        variable_deltas=dict(step.variable_deltas or {}),
        timestamp_ns=getattr(step, "timestamp_ns", None),
        parent_step_id=step.parent_step_id,
        scope_depth=getattr(step, "scope_depth", 0),
        scope_event=getattr(step, "scope_event", None),
    )
    return GraphNode(
        id=f"step_{step.step_id}",
        type=_node_type_for_step(step),
        label=_step_label(step),
        detail=detail,
        position={"x": 0.0, "y": 0.0},
        visual_tier=1,
        collapsed=False,
        cluster_id=step.group_id or "main",
    )


def _build_divergence_nodes(divergences) -> List[GraphNode]:
    nodes: List[GraphNode] = []
    for index, divergence in enumerate(divergences):
        preview = divergence.actual_state if isinstance(divergence.actual_state, dict) else {}
        nodes.append(
            GraphNode(
                id=f"divergence_{index}",
                type="divergence",
                label=_divergence_label(divergence),
                detail=NodeDetail(
                    full_description=divergence.explanation or divergence.actual_behavior,
                    variable_snapshot=preview,
                    code_ref=LineRef(lineno=divergence.symptom_line),
                    role_in_algorithm=divergence.type,
                    why_matters=_divergence_why_it_matters(divergence),
                    invariants_checked=[divergence.expected_behavior],
                    operation="divergence",
                    expected_state=divergence.expected_state,
                    actual_state=divergence.actual_state,
                    missing_state=divergence.missing_state,
                    extra_state=divergence.extra_state,
                    causal_chain=[step.model_dump() if hasattr(step, "model_dump") else step for step in divergence.causal_chain],
                    story_phase="divergence",
                    preview_variables=_focus_variables(preview),
                    hover_summary=_divergence_hover(divergence),
                    group_kind="divergence",
                    is_divergence_path=True,
                    line_number=divergence.symptom_line,
                    code_snippet=None,
                    variables=preview,
                    operation_type="divergence",
                    zoom_levels=["function", "loop", "step"],
                    member_step_ids=[
                        step.step_index if hasattr(step, "step_index") else step.get("step_index")
                        for step in divergence.causal_chain
                        if (step.step_index if hasattr(step, "step_index") else step.get("step_index"))
                    ],
                    group_id="divergence",
                    editable_fields=[],
                    data_dependencies=list(divergence.affected_variables),
                    controls={"editable": False},
                ),
                position={"x": 0.0, "y": 0.0},
                visual_tier=0,
                collapsed=False,
                cluster_id="divergences",
            )
        )
    return nodes


def _build_story_edges(intent_node: GraphNode, function_nodes: List[GraphNode], loop_nodes: List[GraphNode], execution_nodes: List[GraphNode]) -> List[GraphEdge]:
    story_nodes = sorted(function_nodes + loop_nodes, key=_story_sort_key)
    if not story_nodes and execution_nodes:
        story_nodes = [execution_nodes[0]]
    edges: List[GraphEdge] = []
    if story_nodes:
        edges.append(_edge(edge_id=f"{intent_node.id}->{story_nodes[0].id}", source=intent_node.id, target=story_nodes[0].id, edge_type="intent_alignment", label="expected flow", weight=1.4))
        for previous, current in zip(story_nodes, story_nodes[1:]):
            edges.append(_edge(edge_id=f"{previous.id}->{current.id}", source=previous.id, target=current.id, edge_type="control_flow", label="next phase", weight=1.1))
    return edges


def _build_group_edges(function_nodes: List[GraphNode], loop_nodes: List[GraphNode], steps: Sequence[Any]) -> List[GraphEdge]:
    edges: List[GraphEdge] = []
    first_step_by_function: Dict[str, str] = {}
    first_step_by_loop: Dict[str, str] = {}
    for step in steps:
        if step.function_context and step.function_context != "<module>" and step.function_context not in first_step_by_function:
            first_step_by_function[step.function_context] = f"step_{step.step_id}"
        if step.group_id and step.group_id.startswith("loop:") and step.group_id not in first_step_by_loop:
            first_step_by_loop[step.group_id] = f"step_{step.step_id}"

    for function_node in function_nodes:
        target_id = first_step_by_function.get(function_node.detail.function_context or "")
        if target_id:
            edges.append(_edge(edge_id=f"{function_node.id}->{target_id}", source=function_node.id, target=target_id, edge_type="call", label="expand", weight=1.0))

    for loop_node in loop_nodes:
        target_id = first_step_by_loop.get(loop_node.detail.group_id or "")
        if target_id:
            edges.append(_edge(edge_id=f"{loop_node.id}->{target_id}", source=loop_node.id, target=target_id, edge_type="intent_alignment", label="expand", weight=1.0))
    return edges


def _build_control_flow_edges(steps: Sequence[Any]) -> List[GraphEdge]:
    edges: List[GraphEdge] = []
    for previous, current in zip(steps, steps[1:]):
        edge_type = "loop_back" if previous.group_id and previous.group_id == current.group_id and previous.group_id.startswith("loop:") else "control_flow"
        edges.append(
            _edge(
                edge_id=f"step_{previous.step_id}->step_{current.step_id}",
                source=f"step_{previous.step_id}",
                target=f"step_{current.step_id}",
                edge_type=edge_type,
                label="next",
                weight=1.0,
            )
        )
    return edges


def _build_data_flow_edges(steps: Sequence[Any]) -> List[GraphEdge]:
    last_writer: Dict[str, int] = {}
    edges: List[GraphEdge] = []
    for step in steps:
        target = f"step_{step.step_id}"
        emitted = 0
        for access in list(step.read_accesses or step.data_dependencies or []):
            base = _base_access_name(access)
            source_step_id = last_writer.get(base)
            if source_step_id is None or source_step_id == step.step_id:
                continue
            edges.append(
                _edge(
                    edge_id=f"step_{source_step_id}->{target}:{base}",
                    source=f"step_{source_step_id}",
                    target=target,
                    edge_type="data_flow",
                    label=base,
                    weight=0.8,
                    variables=[base],
                )
            )
            emitted += 1
            if emitted >= MAX_DATA_EDGES_PER_STEP:
                break
        for access in step.write_accesses or step.writes:
            last_writer[_base_access_name(access)] = step.step_id
    return edges


def _build_divergence_edges(execution_nodes: List[GraphNode], divergence_nodes: List[GraphNode], divergences) -> List[GraphEdge]:
    edges: List[GraphEdge] = []
    node_by_step = {node.detail.step: node.id for node in execution_nodes if node.detail.step is not None}
    for divergence_node, divergence in zip(divergence_nodes, divergences):
        source_id = None
        for causal_step in reversed(divergence.causal_chain):
            step_index = causal_step.step_index if hasattr(causal_step, "step_index") else causal_step.get("step_index")
            if step_index in node_by_step:
                source_id = node_by_step[step_index]
                break
        if source_id is None:
            for execution_node in execution_nodes:
                if execution_node.detail.line_number in {divergence.first_occurrence_line, divergence.symptom_line}:
                    source_id = execution_node.id
                    break
        if source_id is None and execution_nodes:
            source_id = execution_nodes[-1].id
        if source_id:
            edges.append(
                _edge(
                    edge_id=f"{source_id}->{divergence_node.id}",
                    source=source_id,
                    target=divergence_node.id,
                    edge_type="intent_violation",
                    label=divergence.type,
                    animated=True,
                    weight=1.8,
                    variables=list(divergence.affected_variables),
                )
            )
    return edges


def _build_level_metadata(intent_node: GraphNode, function_nodes: List[GraphNode], loop_nodes: List[GraphNode], execution_nodes: List[GraphNode], divergence_nodes: List[GraphNode]) -> Dict[str, List[str]]:
    return {
        "function": [intent_node.id] + [node.id for node in function_nodes] + [node.id for node in divergence_nodes],
        "loop": [intent_node.id] + [node.id for node in function_nodes + loop_nodes + divergence_nodes],
        "step": [intent_node.id] + [node.id for node in function_nodes + loop_nodes + execution_nodes + divergence_nodes],
        "data": [edge.id for edge in []],
        "all": [intent_node.id] + [node.id for node in function_nodes + loop_nodes + execution_nodes + divergence_nodes],
    }


def _build_cluster_metadata(nodes: Sequence[GraphNode]) -> Dict[str, Dict[str, Any]]:
    grouped: Dict[str, List[str]] = defaultdict(list)
    for node in nodes:
        if node.cluster_id:
            grouped[node.cluster_id].append(node.id)
    return {
        cluster_id: {"node_ids": node_ids, "size": len(node_ids)}
        for cluster_id, node_ids in grouped.items()
    }


def _build_group_metadata(function_nodes: List[GraphNode], loop_nodes: List[GraphNode], steps: Sequence[Any]) -> Dict[str, Dict[str, Any]]:
    step_ids_by_group: Dict[str, List[int]] = defaultdict(list)
    for step in steps:
        if step.group_id:
            step_ids_by_group[step.group_id].append(step.step_id)

    groups: Dict[str, Dict[str, Any]] = {}
    for node in function_nodes + loop_nodes:
        if not node.detail.group_id:
            continue
        groups[node.detail.group_id] = {
            "label": node.label,
            "kind": node.detail.group_kind,
            "member_step_ids": list(step_ids_by_group.get(node.detail.group_id, [])),
            "line_number": node.detail.line_number,
            "zoom_levels": list(node.detail.zoom_levels),
        }
    return groups


def _story_outline(intent, function_nodes: List[GraphNode], loop_nodes: List[GraphNode], divergences) -> List[str]:
    story = [f"Intent: {intent.programmer_goal}"]
    story.extend(node.detail.hover_summary or node.label for node in function_nodes[:4])
    story.extend(node.detail.hover_summary or node.label for node in loop_nodes[:6])
    if divergences:
        story.extend(
            f"Divergence: {divergence.type} at line {divergence.first_occurrence_line}"
            for divergence in divergences[:3]
        )
    return story


def _divergence_path_step_ids(selected_steps: Sequence[Any], divergences) -> set[int]:
    step_ids: set[int] = set()
    steps_by_line: Dict[int, List[int]] = defaultdict(list)
    for step in selected_steps:
        steps_by_line[step.lineno].append(step.step_id)
    for divergence in divergences:
        for causal_step in divergence.causal_chain:
            step_index = causal_step.step_index if hasattr(causal_step, "step_index") else causal_step.get("step_index")
            if step_index:
                step_ids.add(step_index)
        step_ids.update(steps_by_line.get(divergence.first_occurrence_line, []))
        step_ids.update(steps_by_line.get(divergence.symptom_line, []))
    return step_ids


def _node_type_for_step(step) -> str:
    if step.context == "RECURSION":
        if step.event_type == "return" or step.operation == "return":
            return "recursion_base"
        return "recursion_call"
    if step.event_type == "call":
        return "function_entry"
    if step.event_type == "return" or step.operation == "return":
        return "function_exit"
    if step.operation == "loop_header":
        return "loop_header"
    if step.context == "LOOP":
        return "loop_iteration"
    return "execution"


def _step_story(step) -> str:
    parts = [step.explanation or "Execution advances by one deterministic step."]
    if step.code_snippet:
        parts.append(f"Code: `{step.code_snippet}`.")
    if step.write_accesses:
        parts.append(f"Writes: {', '.join(step.write_accesses[:3])}.")
    if step.read_accesses:
        parts.append(f"Reads: {', '.join(step.read_accesses[:3])}.")
    if step.iteration_index is not None:
        parts.append(f"Iteration {step.iteration_index}.")
    if step.function_context and step.function_context != "<module>":
        parts.append(f"Function context: {step.function_context}.")
    return " ".join(parts)


def _hover_summary_for_step(step, preview: Dict[str, Any]) -> str:
    preview_text = ", ".join(f"{key}={_short_value(value)}" for key, value in preview.items())
    base = f"Step {step.step_id} at line {step.lineno}: {step.description}"
    return f"{base} | {preview_text}" if preview_text else base


def _step_label(step) -> str:
    prefix = f"[{step.step_id}]"
    if step.iteration_index is not None:
        prefix += f" iter {step.iteration_index}"
    if step.function_context and step.function_context != "<module>":
        prefix += f" {step.function_context}"
    return f"{prefix} {step.description or f'line {step.lineno}'}"


def _why_step_matters(step) -> str:
    if step.write_accesses:
        return "This step mutates semantic state that later decisions depend on."
    if step.read_accesses:
        return "This step consumes previously computed state, so earlier errors can surface here."
    return "This step advances control flow toward the final result."


def _relevant_invariants(intent, step) -> List[str]:
    invariants = [item.description for item in getattr(intent, "invariants", [])]
    if step.context == "LOOP":
        return invariants[:2]
    return invariants[:1]


def _story_sort_key(node: GraphNode) -> tuple[int, int]:
    lineno = node.detail.line_number or (node.detail.code_ref.lineno if node.detail.code_ref else 10**9)
    return lineno, node.visual_tier


def _focus_variables(snapshot: Dict[str, Any], preferred: Iterable[str] | None = None) -> Dict[str, Any]:
    ordered = list(preferred or [])
    preview: Dict[str, Any] = {}
    for name in ordered:
        base = _base_access_name(name)
        if base in snapshot and base not in preview:
            preview[base] = snapshot[base]
        if name in snapshot and name not in preview:
            preview[name] = snapshot[name]
        if len(preview) >= 4:
            return preview
    for key, value in snapshot.items():
        if key not in preview:
            preview[key] = value
        if len(preview) >= 4:
            break
    return preview


def _base_access_name(access: str) -> str:
    return access.split("[", 1)[0].split(".", 1)[0]


def _short_value(value: Any) -> str:
    text = repr(value)
    if len(text) > 50:
        return text[:47] + "..."
    return text


def _algorithm_title(name: str) -> str:
    pretty = name.replace("_", " ").title()
    for source, target in {"Dp": "DP", "Bfs": "BFS", "Dfs": "DFS", "Mst": "MST"}.items():
        pretty = pretty.replace(source, target)
    return pretty


def _divergence_label(divergence) -> str:
    label_map = {
        "WINDOW_INCOMPLETENESS": "Missing final window",
        "PREMATURE_TERMINATION": "Search stops too early",
        "RESULT_APPENDS_REFERENCE": "Path stored by reference",
        "WRONG_VISITED_CHECK": "Visited marked too late",
        "BFS_VISITED_LATE": "Visited marked after enqueue",
        "WRONG_BASE_CASE_VALUE": "Wrong base case value",
        "LOOP_BOUND_ERROR": "Loop bound error",
        "LOOP_MISSING_LAST_ITERATION": "Missing final iteration",
        "OFF_BY_ONE": "Off-by-one boundary",
        "OFF_BY_ONE_BOUND": "Off-by-one boundary",
        "HEAP_INDEX_ERROR": "Wrong heap index",
        "WRONG_INDEX_ACCESS": "Wrong index access",
        "WRONG_STATE_SELECTION": "Wrong state selection",
        "WRONG_CONDITION_CHECK": "Wrong condition check",
        "SEMANTIC_MISMATCH": "Semantic mismatch",
        "DP_STATE_INCONSISTENCY": "DP state inconsistency",
    }
    label = label_map.get(divergence.type, divergence.type.replace("_", " ").title())
    if isinstance(getattr(divergence, "evidence", None), dict) and divergence.evidence.get("source") == "LLM_SECOND_PASS":
        return f"Semantic alert: {label.lower()}"
    return label


def _divergence_hover(divergence) -> str:
    if isinstance(getattr(divergence, "evidence", None), dict) and divergence.evidence.get("source") == "LLM_SECOND_PASS":
        return f"Gemini second pass: {divergence.divergence_point or divergence.type}"
    return divergence.divergence_point or divergence.type


def _divergence_why_it_matters(divergence) -> str:
    if isinstance(getattr(divergence, "evidence", None), dict) and divergence.evidence.get("source") == "LLM_SECOND_PASS":
        return (
            "This semantic alert comes from Gemini's second pass. "
            f"{divergence.algorithm_context}"
        )
    return divergence.algorithm_context


def _edge(
    *,
    edge_id: str,
    source: str,
    target: str,
    edge_type: str,
    label: Optional[str],
    animated: bool = False,
    weight: float = 1.0,
    variables: Optional[List[str]] = None,
) -> GraphEdge:
    return GraphEdge(
        id=edge_id,
        source=source,
        target=target,
        type=edge_type,
        label=label,
        animated=animated,
        weight=weight,
        variables=variables or [],
    )
