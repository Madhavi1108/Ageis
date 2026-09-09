"""FastAPI dependency for the GitHub client.

Separated so tests can ``app.dependency_overrides[get_github_client]`` a client
wired to an ``httpx.MockTransport`` -- mirrors app/ai/deps.py.
"""

from __future__ import annotations

from fastapi import Depends

from app.core.circuit_breaker import get_breaker
from app.core.config import Settings, get_settings
from app.github.client import GitHubClient


def build_github_client(settings: Settings) -> GitHubClient:
    token = (
        settings.github_token.get_secret_value()
        if settings.github_token is not None
        else None
    )
    return GitHubClient(
        token=token,
        base_url=settings.github_api_base_url,
        timeout_s=settings.github_timeout_s,
        max_retries=settings.github_max_retries,
        breaker=get_breaker(
            "github",
            fail_threshold=settings.circuit_breaker_fail_threshold,
            reset_after_s=settings.circuit_breaker_reset_s,
        ),
    )


def get_github_client(
    settings: Settings = Depends(get_settings),
) -> GitHubClient:
    return build_github_client(settings)
