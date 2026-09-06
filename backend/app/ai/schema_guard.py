"""Schema validation with one repair round. Ported from
backend/aegis/ai/schema_guard.py (docs/AI_AGENT_DESIGN.md Section 3, ADR-0005):
"one repair round on invalid output then clean failure -- no silent
best-effort".
"""

from __future__ import annotations

from typing import Any, Callable

from pydantic import BaseModel, ValidationError


class AIOutputInvalid(Exception):
    """Raised when an AI response fails schema validation even after one repair
    round (or immediately, if no repair function was given)."""


def validate_with_repair(
    raw: dict[str, Any],
    schema: type[BaseModel],
    repair_fn: Callable[[dict[str, Any], str], dict[str, Any]] | None = None,
) -> BaseModel:
    """Validate ``raw`` against ``schema``. On failure call
    ``repair_fn(raw, error_message)`` exactly once for a corrected dict and
    validate that; a second failure raises ``AIOutputInvalid``."""
    try:
        return schema.model_validate(raw)
    except ValidationError as first_error:
        if repair_fn is None:
            raise AIOutputInvalid(str(first_error)) from first_error
        try:
            repaired = repair_fn(raw, str(first_error))
            return schema.model_validate(repaired)
        except ValidationError as second_error:
            raise AIOutputInvalid(
                f"schema still invalid after one repair round: {second_error}"
            ) from second_error
