"""AI-layer error types. ``AIOutputInvalid`` (schema_guard) is re-exported here
so callers have one import site for "the model let us down"."""

from __future__ import annotations

from fastapi import status

from app.ai.schema_guard import AIOutputInvalid
from app.core.errors import AppError

__all__ = ["AIOutputInvalid", "AIProviderNotConfiguredError"]


class AIProviderNotConfiguredError(AppError):
    """The selected ``ai_provider`` cannot run in this environment (missing key,
    opt-in flag, or an unimplemented provider)."""

    def __init__(self, message: str) -> None:
        super().__init__(
            "AI_PROVIDER_NOT_CONFIGURED",
            message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
