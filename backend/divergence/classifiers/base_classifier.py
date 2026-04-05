from __future__ import annotations

import ast
import uuid
from typing import Any, Callable, Dict, Iterable, List, Optional

from backend.api.models import CausalStep, Divergence, IntentModel


class BaseClassifier:
    def applicable(self, intent: IntentModel) -> bool:
        return True

    def detect(self, trace, intent, expectation, cfg) -> List[Divergence]:
        return []

    def _source(self, cfg: Dict[str, Any] | None) -> str:
        return (cfg or {}).get("source", "")

    def _tree(self, cfg: Dict[str, Any] | None) -> ast.AST | None:
        return (cfg or {}).get("ast")

    def _loops(self, cfg: Dict[str, Any] | None) -> List[Dict[str, Any]]:
        return (cfg or {}).get("loops", [])

    def _first_loop_line(self, cfg: Dict[str, Any] | None, default: int = 1) -> int:
        loops = self._loops(cfg)
        if not loops:
            return default
        return min(loop.get("header_line", default) for loop in loops)

    def _iter_nodes(
        self,
        cfg: Dict[str, Any] | None,
        node_type: type[ast.AST] | tuple[type[ast.AST], ...] | None = None,
    ) -> Iterable[ast.AST]:
        tree = self._tree(cfg)
        if tree is None:
            return []
        nodes = ast.walk(tree)
        if node_type is None:
            return nodes
        return (node for node in nodes if isinstance(node, node_type))

    def _find_first(
        self,
        cfg: Dict[str, Any] | None,
        node_type: type[ast.AST] | tuple[type[ast.AST], ...],
        predicate: Callable[[ast.AST], bool] | None = None,
    ) -> ast.AST | None:
        for node in self._iter_nodes(cfg, node_type):
            if predicate is None or predicate(node):
                return node
        return None

    def _find_line_containing(self, cfg: Dict[str, Any] | None, needle: str, default: int = 1) -> int:
        for lineno, line in enumerate(self._source(cfg).splitlines(), start=1):
            if needle in line:
                return lineno
        return default

    def _ast_text(self, node: ast.AST | None) -> str:
        if node is None:
            return ""
        try:
            return ast.unparse(node)
        except Exception:
            return ""

    def _make_divergence(
        self,
        *,
        divergence_type: str,
        severity: str,
        line: int,
        expected_behavior: str,
        actual_behavior: str,
        algorithm_context: str,
        fix_suggestion: str,
        affected_variables: List[str] | None = None,
        affected_lines: List[int] | None = None,
        causal_chain: List[CausalStep] | None = None,
        symptom_line: Optional[int] = None,
    ) -> Divergence:
        return Divergence(
            divergence_id=str(uuid.uuid4()),
            type=divergence_type,
            severity=severity,
            causal_chain=causal_chain or [],
            first_occurrence_line=line,
            symptom_line=symptom_line or line,
            expected_behavior=expected_behavior,
            actual_behavior=actual_behavior,
            affected_variables=affected_variables or [],
            affected_lines=affected_lines or [line],
            algorithm_context=algorithm_context,
            fix_suggestion=fix_suggestion,
        )

    def _make_causal_step(
        self,
        *,
        step_index: int,
        description: str,
        lineno: int,
        why_this_matters: str,
        variable_state: Dict[str, Any] | None = None,
    ) -> CausalStep:
        return CausalStep(
            step_index=step_index,
            description=description,
            lineno=lineno,
            variable_state=variable_state or {},
            why_this_matters=why_this_matters,
        )
