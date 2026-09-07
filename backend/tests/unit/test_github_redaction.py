"""Phase 19 unit: a GitHub token never reaches a log record.

Does not go through the logging framework (global ``logging.disable`` state
from other tests makes that flaky) -- it captures what ``log_github_call``
hands the logger and asserts the redaction contract directly.
"""

from __future__ import annotations

import json

import httpx

from app.core.security import contains_secret
from app.github import request_log
from app.github.client import GitHubClient

_TOKEN = "ghp_" + "z" * 36


class _RecordingLogger:
    def __init__(self) -> None:
        self.records: list[tuple[str, dict]] = []

    def info(self, msg: str, *, extra: dict | None = None) -> None:
        self.records.append((msg, extra or {}))


def _run_with_recorder(fn):
    rec = _RecordingLogger()
    original = request_log._logger
    request_log._logger = rec
    try:
        fn()
    finally:
        request_log._logger = original
    return rec


def test_client_call_logs_only_the_path_and_never_the_token():
    def go() -> None:
        client = GitHubClient(
            token=_TOKEN,
            base_url=f"https://api.github.test/secret-{_TOKEN}",  # token even in the URL
            transport=httpx.MockTransport(
                lambda r: httpx.Response(200, json={"full_name": "o/r"})
            ),
        )
        client.get_repo("o", "r")
        client.close()

    rec = _run_with_recorder(go)

    assert [m for m, _ in rec.records] == ["github_call"]
    extra = rec.records[0][1]
    assert extra["gh_url"] == "/repos/o/r"  # path only, no host, no token
    assert extra["gh_status"] == 200
    assert extra["gh_outcome"] == "ok"

    blob = json.dumps(rec.records)
    assert _TOKEN not in blob
    assert not contains_secret(blob)


def test_request_log_redacts_a_secret_that_slips_into_the_url():
    rec = _run_with_recorder(
        lambda: request_log.log_github_call(
            method="GET",
            url=f"/repos/o/r?token={_TOKEN}",
            status=200,
            latency_ms=1,
            outcome="ok",
        )
    )
    logged_url = rec.records[0][1]["gh_url"]
    assert _TOKEN not in logged_url
    assert "REDACTED" in logged_url
