"""Phase 19 unit: the GitHub REST client against a mocked transport --
status-code mapping, retries, transport-error mapping.
"""

from __future__ import annotations

import httpx
import pytest

from app.github.client import GitHubClient
from app.github.errors import (
    GitHubConflictError,
    GitHubNetworkError,
    GitHubNotFoundError,
    GitHubPermissionError,
    GitHubRateLimitError,
    GitHubUnavailableError,
)


def _client(handler) -> GitHubClient:
    return GitHubClient(
        token="ghp_" + "a" * 36,
        base_url="https://api.github.test",
        max_retries=2,
        transport=httpx.MockTransport(handler),
    )


def test_get_repo_ok():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"].startswith("Bearer ")
        return httpx.Response(200, json={"full_name": "o/r", "default_branch": "main"})

    with _client(handler) as c:
        assert c.get_repo("o", "r")["full_name"] == "o/r"


def test_create_pull_201_parsed():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            201, json={"html_url": "https://gh.test/o/r/pull/7", "number": 7}
        )

    with _client(handler) as c:
        pr = c.create_pull("o", "r", title="t", head="h", base="main", body="b")
    assert pr.url.endswith("/pull/7")
    assert pr.number == 7


@pytest.mark.parametrize(
    "status, err",
    [
        (403, GitHubPermissionError),
        (404, GitHubNotFoundError),
        (409, GitHubConflictError),
        (422, GitHubConflictError),
        (429, GitHubRateLimitError),
    ],
)
def test_status_mapping(status, err):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"message": "nope"})

    with _client(handler) as c:
        with pytest.raises(err):
            c.get_repo("o", "r")


def test_403_ratelimit_marker_is_ratelimit():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            json={"message": "API rate limit exceeded"},
            headers={"X-RateLimit-Remaining": "0"},
        )

    with _client(handler) as c:
        with pytest.raises(GitHubRateLimitError):
            c.get_repo("o", "r")


def test_retry_then_success():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(503, headers={"Retry-After": "0"}, json={})
        return httpx.Response(200, json={"full_name": "o/r"})

    with _client(handler) as c:
        assert c.get_repo("o", "r")["full_name"] == "o/r"
    assert calls["n"] == 3


def test_retry_exhausted_raises_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, headers={"Retry-After": "0"}, json={})

    with _client(handler) as c:
        with pytest.raises(GitHubUnavailableError):
            c.get_repo("o", "r")


def test_transport_error_maps_to_network_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    with _client(handler) as c:
        with pytest.raises(GitHubNetworkError):
            c.get_repo("o", "r")


def test_get_ref_returns_sha():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"object": {"sha": "abc123"}})

    with _client(handler) as c:
        assert c.get_ref("o", "r", "heads/main") == "abc123"


def test_put_file_returns_commit_sha():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "PUT"
        return httpx.Response(201, json={"commit": {"sha": "def456"}})

    with _client(handler) as c:
        sha = c.put_file(
            "o", "r", "invoice.py", message="m", content_bytes=b"x", branch="b"
        )
    assert sha == "def456"
