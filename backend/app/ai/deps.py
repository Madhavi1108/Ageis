"""FastAPI dependency for the configured AI provider.

Separated from provider.py so tests can ``app.dependency_overrides[get_ai_provider]``
a pre-loaded MockProvider without touching global state.
"""

from __future__ import annotations

from fastapi import Depends

from app.ai.provider import AIProvider, get_provider
from app.core.config import Settings, get_settings


def get_ai_provider(
    settings: Settings = Depends(get_settings),
) -> AIProvider | None:
    return get_provider(settings)
