from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from backend.api.models import AnalysisResponse

SEVERITY_WEIGHTS = {
    "CRITICAL": 1.0,
    "HIGH": 0.75,
    "MEDIUM": 0.45,
    "LOW": 0.2,
}

RECURSION_ERROR_KEYS = {
    "base_case_missing",
    "wrong_base_case_value",
    "wrong_recursive_return",
    "memoization_miss",
    "dp_transition_error",
    "dp_state_inconsistency",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _normalize_user_id(user_id: str | None) -> str | None:
    if user_id is None:
        return None
    normalized = user_id.strip()
    return normalized or None


def _path_safe_user_id(user_id: str) -> str:
    forbidden = '<>:"/\\|?*'
    safe = user_id
    for char in forbidden:
        safe = safe.replace(char, "_")
    return safe


def _coerce_float(value: Any) -> float:
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return 0.0


def _normalize_divergence_type(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text.lower()


def _default_traits() -> Dict[str, bool]:
    return {
        "optimistic_executor": False,
        "off_by_one_prone": False,
        "state_mutation_errors": False,
        "recursion_blind": False,
        "index_confusion": False,
    }


def _default_fingerprint(user_id: str) -> Dict[str, Any]:
    return {
        "user_id": user_id,
        "session_count": 0,
        "error_vector": {},
        "algorithm_blindspots": [],
        "dominant_error_class": None,
        "cognitive_traits": _default_traits(),
        "last_updated": _utc_now_iso(),
    }


def _derive_traits(error_vector: Dict[str, float], dominant_error_class: str | None) -> Dict[str, bool]:
    off_by_one_signal = error_vector.get("off_by_one", 0.0) + error_vector.get("off_by_one_bound", 0.0)
    boundary_signal = (
        error_vector.get("missing_null_check", 0.0)
        + error_vector.get("missing_edge_case", 0.0)
        + error_vector.get("loop_bound_error", 0.0)
        + error_vector.get("loop_missing_last_iteration", 0.0)
        + error_vector.get("off_by_one_bound", 0.0)
    )
    mutation_signal = max(
        error_vector.get("missing_state_update", 0.0),
        error_vector.get("wrong_window_update", 0.0),
    )
    recursion_signal = sum(error_vector.get(key, 0.0) for key in RECURSION_ERROR_KEYS)

    return {
        "optimistic_executor": boundary_signal > 0.3,
        "off_by_one_prone": off_by_one_signal > 0.3,
        "state_mutation_errors": mutation_signal > 0.25,
        "recursion_blind": bool(dominant_error_class in RECURSION_ERROR_KEYS or recursion_signal > 0.35),
        "index_confusion": error_vector.get("wrong_index_access", 0.0) > 0.25,
    }


class FingerprintStore:
    def __init__(self, base_dir: str | Path | None = None) -> None:
        self.base_dir = Path(base_dir) if base_dir is not None else Path(__file__).resolve().parents[2] / ".fingerprints"

    def load(self, user_id: str) -> dict:
        normalized_user_id = _normalize_user_id(user_id)
        if not normalized_user_id:
            return {}

        try:
            path = self._path_for_user(normalized_user_id)
            if not path.exists():
                return _default_fingerprint(normalized_user_id)

            with path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except Exception:
            return _default_fingerprint(normalized_user_id)

        if not isinstance(payload, dict):
            return _default_fingerprint(normalized_user_id)
        return self._coerce_fingerprint(normalized_user_id, payload)

    def save(self, user_id: str, fingerprint: dict) -> None:
        normalized_user_id = _normalize_user_id(user_id)
        if not normalized_user_id:
            return

        temp_path: Path | None = None
        try:
            self.base_dir.mkdir(parents=True, exist_ok=True)
            final_path = self._path_for_user(normalized_user_id)
            payload = self._coerce_fingerprint(normalized_user_id, fingerprint)

            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.base_dir,
                delete=False,
                prefix=f"{_path_safe_user_id(normalized_user_id)}-",
                suffix=".tmp",
            ) as handle:
                json.dump(payload, handle, ensure_ascii=True, indent=2, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
                temp_path = Path(handle.name)

            os.replace(temp_path, final_path)
        except Exception:
            if temp_path is not None:
                try:
                    temp_path.unlink(missing_ok=True)
                except Exception:
                    pass

    def update(self, user_id: str, analysis_result: AnalysisResponse) -> dict:
        normalized_user_id = _normalize_user_id(user_id)
        if not normalized_user_id:
            return {}

        try:
            fingerprint = self.load(normalized_user_id)
            current_vector = fingerprint.get("error_vector", {}) if isinstance(fingerprint, dict) else {}
            error_vector = {
                key: round(_coerce_float(value) * 0.85, 4)
                for key, value in current_vector.items()
                if _normalize_divergence_type(key)
            }

            for divergence in getattr(analysis_result, "divergences", []) or []:
                divergence_type = _normalize_divergence_type(getattr(divergence, "type", None))
                if not divergence_type:
                    continue
                severity = str(getattr(divergence, "severity", "LOW") or "LOW").upper()
                weight = SEVERITY_WEIGHTS.get(severity, 0.2)
                error_vector[divergence_type] = round(error_vector.get(divergence_type, 0.0) + weight, 4)

            error_vector = {
                key: value
                for key, value in error_vector.items()
                if value > 0
            }

            algorithm_blindspots = self._coerce_string_list(fingerprint.get("algorithm_blindspots", []))
            algorithm_name = self._extract_algorithm_name(analysis_result)
            divergence_score = self._extract_divergence_score(analysis_result)
            if algorithm_name and divergence_score > 0.4 and algorithm_name not in algorithm_blindspots:
                algorithm_blindspots.append(algorithm_name)

            dominant_error_class = max(error_vector, key=error_vector.get) if error_vector else None
            updated = {
                "user_id": normalized_user_id,
                "session_count": int(fingerprint.get("session_count", 0) or 0) + 1,
                "error_vector": error_vector,
                "algorithm_blindspots": algorithm_blindspots,
                "dominant_error_class": dominant_error_class,
                "cognitive_traits": _derive_traits(error_vector, dominant_error_class),
                "last_updated": _utc_now_iso(),
            }
            self.save(normalized_user_id, updated)
            return updated
        except Exception:
            return self.load(normalized_user_id)

    def _path_for_user(self, user_id: str) -> Path:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        return self.base_dir / f"{_path_safe_user_id(user_id)}.json"

    def _coerce_fingerprint(self, user_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        error_vector_raw = payload.get("error_vector", {})
        error_vector = {}
        if isinstance(error_vector_raw, dict):
            for key, value in error_vector_raw.items():
                divergence_type = _normalize_divergence_type(key)
                if divergence_type:
                    error_vector[divergence_type] = round(_coerce_float(value), 4)

        dominant_error_class = payload.get("dominant_error_class")
        if dominant_error_class is not None:
            dominant_error_class = _normalize_divergence_type(dominant_error_class)
        if dominant_error_class is None and error_vector:
            dominant_error_class = max(error_vector, key=error_vector.get)

        fingerprint = _default_fingerprint(user_id)
        fingerprint.update(
            {
                "user_id": user_id,
                "session_count": int(payload.get("session_count", 0) or 0),
                "error_vector": error_vector,
                "algorithm_blindspots": self._coerce_string_list(payload.get("algorithm_blindspots", [])),
                "dominant_error_class": dominant_error_class,
                "cognitive_traits": _derive_traits(error_vector, dominant_error_class),
                "last_updated": str(payload.get("last_updated") or fingerprint["last_updated"]),
            }
        )
        return fingerprint

    def _extract_algorithm_name(self, analysis_result: AnalysisResponse) -> str | None:
        intent_model = getattr(analysis_result, "intent_model", None)
        if intent_model is not None:
            value = getattr(intent_model, "inferred_algorithm", None)
            if value:
                return str(value)

        intent_payload = getattr(analysis_result, "intent", None)
        if isinstance(intent_payload, dict):
            value = intent_payload.get("inferred_algorithm")
            if value:
                return str(value)
        return None

    def _extract_divergence_score(self, analysis_result: AnalysisResponse) -> float:
        metrics = getattr(analysis_result, "metrics", None)
        if metrics is None:
            return 0.0

        value = getattr(metrics, "divergence_severity_score", None)
        if value is None:
            value = getattr(metrics, "divergence_score", None)
        return _coerce_float(value)

    def _coerce_string_list(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []

        cleaned: list[str] = []
        seen: set[str] = set()
        for item in value:
            text = str(item).strip()
            if not text or text in seen:
                continue
            seen.add(text)
            cleaned.append(text)
        return cleaned
