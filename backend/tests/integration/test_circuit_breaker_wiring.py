"""Phase 27 integration: the GitHub client's circuit breaker opens after
repeated upstream failures and then fails fast without touching the network."""

from __future__ import annotations

import httpx
import pytest

from app.core.circuit_breaker import CircuitBreaker, UpstreamUnavailableError
from app.github.client import GitHubClient
from app.github.errors import GitHubNotFoundError, GitHubUnavailableError


class _Counter:
    def __init__(self, status_code: int, body: dict) -> None:
        self.status_code = status_code
        self.body = body
        self.calls = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        return httpx.Response(self.status_code, json=self.body)


def _client(handler, breaker: CircuitBreaker) -> GitHubClient:
    return GitHubClient(
        token=None,
        base_url="https://api.github.test",
        max_retries=0,
        transport=httpx.MockTransport(handler),
        breaker=breaker,
    )


def test_breaker_opens_after_threshold_then_fast_fails():
    handler = _Counter(503, {"message": "unavailable"})
    breaker = CircuitBreaker("github-test", fail_threshold=3, reset_after_s=60.0)
    gh = _client(handler, breaker)

    for _ in range(3):
        with pytest.raises(GitHubUnavailableError):
            gh.get_repo("octo", "demo")
    assert handler.calls == 3
    assert breaker.state == "OPEN"

    # further calls fail fast -- the transport is not touched again
    for _ in range(5):
        with pytest.raises(UpstreamUnavailableError):
            gh.get_repo("octo", "demo")
    assert handler.calls == 3


def test_client_error_does_not_trip_the_breaker():
    handler = _Counter(404, {"message": "nope"})
    breaker = CircuitBreaker("github-test-404", fail_threshold=2, reset_after_s=60.0)
    gh = _client(handler, breaker)

    for _ in range(6):
        with pytest.raises(GitHubNotFoundError):
            gh.get_repo("octo", "missing")
    assert breaker.state == "CLOSED"
    assert handler.calls == 6  # every call still reached the transport
