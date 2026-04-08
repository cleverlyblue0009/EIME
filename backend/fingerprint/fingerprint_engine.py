from __future__ import annotations

from typing import Any, Dict

from backend.api.models import IntentModel
from backend.fingerprint.fingerprint_store import FingerprintStore

RISKY_NONE_NAMES = {"result", "node", "head", "curr", "prev", "val"}


class FingerprintEngine:
    def __init__(self, store: FingerprintStore):
        self.store = store

    def build_prior(self, fingerprint: dict) -> dict:
        if not fingerprint:
            return {
                "classifier_weights": {},
                "suspected_blindspots": [],
                "prompt_addendum": "",
                "blind_spot_lines": [],
            }

        error_vector = fingerprint.get("error_vector", {}) if isinstance(fingerprint, dict) else {}
        dominant_error = fingerprint.get("dominant_error_class")
        classifier_weights = {
            key: 1.5 if key == dominant_error else 1.0
            for key in error_vector
        }

        prompt_addendum = self._build_prompt_addendum(fingerprint)
        return {
            "classifier_weights": classifier_weights,
            "suspected_blindspots": list(fingerprint.get("algorithm_blindspots", [])),
            "prompt_addendum": prompt_addendum,
            "blind_spot_lines": [],
        }

    def predict_blindspot_lines(
        self,
        fingerprint: dict,
        parse_result: dict,
        intent_model: IntentModel,
    ) -> list[dict]:
        if not fingerprint:
            return []

        traits = fingerprint.get("cognitive_traits", {}) if isinstance(fingerprint, dict) else {}
        loops = parse_result.get("loops", []) if parse_result else []
        line_index = parse_result.get("line_index", {}) if parse_result else {}
        call_graph = parse_result.get("call_graph", {}) if parse_result else {}
        var_names = {str(name) for name in (parse_result.get("var_names", set()) if parse_result else set())}

        flagged: Dict[int, Dict[str, str]] = {}

        if traits.get("off_by_one_prone") and loops:
            for loop in loops:
                header_line = self._coerce_line(loop.get("header_line"))
                end_line = self._coerce_line(loop.get("end_line"))
                self._flag(flagged, header_line, "Off-by-one prone near loop boundary", "HIGH")
                self._flag(flagged, end_line, "Off-by-one prone near loop boundary", "HIGH")

        if traits.get("optimistic_executor") and var_names & RISKY_NONE_NAMES:
            for var_name in sorted(var_names & RISKY_NONE_NAMES):
                assign_line = self._first_assignment_line(line_index, var_name)
                self._flag(
                    flagged,
                    assign_line,
                    f"Optimistic executor risk around initial '{var_name}' assignment",
                    "MEDIUM",
                )

        inferred_algorithm = (getattr(intent_model, "inferred_algorithm", "") or "").lower()
        if traits.get("recursion_blind") and ("recursion" in inferred_algorithm or "dp" in inferred_algorithm):
            recursive_lines = call_graph.get("recursive_lines", []) if isinstance(call_graph, dict) else []
            for line in recursive_lines:
                self._flag(flagged, self._coerce_line(line), "Recursion-heavy control flow is a historical blind spot", "HIGH")

        if traits.get("index_confusion") and loops:
            for loop in loops:
                start = self._coerce_line(loop.get("header_line"))
                end = self._coerce_line(loop.get("end_line"))
                if start is None or end is None:
                    continue
                for lineno, payload in sorted(line_index.items()):
                    parsed_line = self._coerce_line(lineno)
                    if parsed_line is None or parsed_line < start or parsed_line > end:
                        continue
                    accesses = list(payload.get("read_accesses", [])) + list(payload.get("write_accesses", []))
                    if any("[" in str(access) and "]" in str(access) for access in accesses):
                        self._flag(flagged, parsed_line, "Index-confusion risk around subscript access inside loop", "HIGH")

        return [
            {
                "line": line,
                "risk_reason": payload["risk_reason"],
                "severity": payload["severity"],
            }
            for line, payload in sorted(flagged.items())
        ]

    def _build_prompt_addendum(self, fingerprint: dict) -> str:
        session_count = int(fingerprint.get("session_count", 0) or 0)
        if session_count <= 0:
            return ""

        dominant_error = fingerprint.get("dominant_error_class")
        blindspots = list(fingerprint.get("algorithm_blindspots", []))
        traits = fingerprint.get("cognitive_traits", {}) if isinstance(fingerprint, dict) else {}

        trait_fragments = [
            "often misses loop boundaries" if traits.get("off_by_one_prone") else "",
            "can be overconfident about null or edge-case safety" if traits.get("optimistic_executor") else "",
            "tends to slip on state mutations" if traits.get("state_mutation_errors") else "",
            "needs extra scrutiny on recursive or DP state transitions" if traits.get("recursion_blind") else "",
            "is vulnerable to index-access mistakes" if traits.get("index_confusion") else "",
        ]
        trait_summary = ", ".join(fragment for fragment in trait_fragments if fragment)
        if not trait_summary:
            trait_summary = "has a light but emerging history of repeated divergence patterns"

        sentences = [
            f"This programmer has {session_count} prior session(s), with {trait_summary}.",
        ]
        if dominant_error:
            sentences.append(
                f"The strongest historical error signal is {dominant_error.replace('_', ' ')}, so weigh similar failure modes more carefully."
            )
        else:
            sentences.append("No single dominant error class has fully stabilized yet, but the recurring traits above should still guide extra scrutiny.")
        if blindspots:
            preview = ", ".join(blindspots[:3])
            sentences.append(f"Historical blind spots include {preview}.")
        return " ".join(sentences[:3])

    def _first_assignment_line(self, line_index: Dict[int, Dict[str, Any]], var_name: str) -> int | None:
        for lineno, payload in sorted(line_index.items()):
            writes = {str(name) for name in payload.get("writes", [])}
            if var_name in writes:
                return self._coerce_line(lineno)
        return None

    def _flag(self, flagged: Dict[int, Dict[str, str]], line: int | None, reason: str, severity: str) -> None:
        if line is None or line <= 0:
            return
        existing = flagged.get(line)
        if existing is None:
            flagged[line] = {"risk_reason": reason, "severity": severity}
            return

        reasons = set(part.strip() for part in existing["risk_reason"].split(";") if part.strip())
        reasons.add(reason)
        existing["risk_reason"] = "; ".join(sorted(reasons))
        if self._severity_rank(severity) > self._severity_rank(existing["severity"]):
            existing["severity"] = severity

    def _coerce_line(self, value: Any) -> int | None:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return None
        return parsed if parsed > 0 else None

    def _severity_rank(self, severity: str) -> int:
        return {"HIGH": 2, "MEDIUM": 1}.get(severity, 0)
