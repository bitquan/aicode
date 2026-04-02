"""Typed request/response models for shared app commands."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


def infer_result_status(response_text: str) -> str:
    """Infer a coarse result status from a conversational response."""
    text = (response_text or "").lower()
    if "⚠️" in text or "error" in text or "has issues" in text:
        return "failure"
    if "unable" in text or "partial" in text:
        return "partial"
    return "success"


@dataclass(slots=True)
class ActionRequest:
    """Structured action request shared across CLI, API, and chat surfaces."""

    action: str
    confidence: float = 0.0
    raw_input: str = ""
    params: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        if key == "action":
            return self.action
        if key == "confidence":
            return self.confidence
        if key == "raw_input":
            return self.raw_input or default
        return self.params.get(key, default)

    def to_legacy_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "action": self.action,
            **self.params,
        }
        if self.confidence:
            payload["confidence"] = self.confidence
        if self.raw_input:
            payload["raw_input"] = self.raw_input
        return payload

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "ActionRequest":
        try:
            confidence = float(payload.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0

        params = {
            str(key): value
            for key, value in payload.items()
            if key not in {"action", "confidence", "raw_input"}
        }
        return cls(
            action=str(payload.get("action", "")),
            confidence=confidence,
            raw_input=str(payload.get("raw_input", "") or ""),
            params=params,
        )


@dataclass(slots=True)
class ActionResponse:
    """Structured response shared across app surfaces."""

    action: str
    text: str
    confidence: float = 0.0
    result_status: str = "success"

    @classmethod
    def from_text(
        cls,
        *,
        action: str,
        text: str,
        confidence: float = 0.0,
    ) -> "ActionResponse":
        return cls(
            action=action,
            text=text,
            confidence=confidence,
            result_status=infer_result_status(text),
        )
