from __future__ import annotations

from typing import Any, Dict, List, Sequence

from backend.api.models import AlignmentEntry, IntentStep


class AlignmentEngine:
    def build(self, normalized_trace, intent, divergences) -> tuple[List[IntentStep], List[AlignmentEntry]]:
        intent_steps = self._build_intent_steps(intent)
        divergence_step_ids = self._divergence_step_ids(divergences)
        divergence_lines = {
            line
            for divergence in divergences
            for line in [divergence.first_occurrence_line, divergence.symptom_line]
            if line is not None
        }

        alignments: List[AlignmentEntry] = []
        phase_steps = [step for step in intent_steps if step.phase_type == "phase"]
        for execution_step in getattr(normalized_trace, "steps", []) or []:
            matched = self._match_phase(execution_step, phase_steps)
            relation = "unknown"
            rationale = "No matching intent phase was inferred for this execution step."
            score = 0.35

            if matched is not None:
                relation = "supports"
                rationale = f"This step falls inside the `{matched.label}` intent phase."
                score = 0.78
                if execution_step.step_id in divergence_step_ids or execution_step.lineno in divergence_lines:
                    relation = "violates"
                    rationale = f"This step maps to `{matched.label}` but participates in the detected divergence path."
                    score = 0.22
                elif execution_step.operation_type in {"call", "return"}:
                    relation = "context"
                    rationale = f"This step provides call-frame context for `{matched.label}`."
                    score = 0.58

            alignments.append(
                AlignmentEntry(
                    execution_step_id=execution_step.step_id,
                    intent_step_id=matched.intent_step_id if matched is not None else "intent_goal",
                    relation=relation,
                    score=round(score, 2),
                    rationale=rationale,
                    line_number=execution_step.lineno,
                    function_context=execution_step.function_context,
                )
            )

        return intent_steps, alignments

    def _build_intent_steps(self, intent) -> List[IntentStep]:
        steps: List[IntentStep] = [
            IntentStep(
                intent_step_id="intent_goal",
                label="Program Goal",
                description=intent.programmer_goal,
                phase_type="goal",
                invariants=[item.description for item in getattr(intent, "invariants", [])],
                algorithm_role=intent.inferred_algorithm,
                confidence=round(getattr(intent, "confidence", 0.0), 2),
            )
        ]

        phases = getattr(intent, "algorithm_phase_sequence", []) or []
        for index, phase in enumerate(phases, start=1):
            steps.append(
                IntentStep(
                    intent_step_id=f"intent_phase_{index}",
                    label=phase.phase_name,
                    description=phase.description,
                    phase_type="phase",
                    start_line=phase.start_line,
                    end_line=phase.end_line,
                    invariants=[item.description for item in getattr(intent, "invariants", [])[:2]],
                    algorithm_role=intent.inferred_algorithm,
                    confidence=round(getattr(intent, "confidence", 0.0), 2),
                )
            )

        for index, invariant in enumerate(getattr(intent, "invariants", []) or [], start=1):
            steps.append(
                IntentStep(
                    intent_step_id=f"intent_invariant_{index}",
                    label=f"Invariant {index}",
                    description=invariant.description,
                    phase_type="invariant",
                    invariants=[invariant.description],
                    algorithm_role=intent.inferred_algorithm,
                    confidence=round(getattr(intent, "confidence", 0.0), 2),
                )
            )

        return steps

    def _match_phase(self, execution_step, phases: Sequence[IntentStep]) -> IntentStep | None:
        for phase in phases:
            if phase.start_line is None or phase.end_line is None:
                continue
            if phase.start_line <= execution_step.lineno <= phase.end_line:
                return phase
        return phases[0] if phases else None

    def _divergence_step_ids(self, divergences) -> set[int]:
        step_ids: set[int] = set()
        for divergence in divergences:
            for item in divergence.causal_chain:
                if hasattr(item, "step_index") and item.step_index:
                    step_ids.add(item.step_index)
                elif isinstance(item, dict) and item.get("step_index"):
                    step_ids.add(item["step_index"])
        return step_ids
