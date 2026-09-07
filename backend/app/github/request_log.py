"""Redacted GitHub request logging -- mirrors app/ai/request_log.py.

One structured record per call: method, URL, status, latency, outcome. Never
the request/response body, never headers. ``redact`` is applied to the URL
defensively (a token must never appear there, but belt-and-braces).
"""

from __future__ import annotations

import logging

from app.core.security import redact

_logger = logging.getLogger("app.github")


def log_github_call(
    *,
    method: str,
    url: str,
    status: int | None,
    latency_ms: int,
    outcome: str,
) -> None:
    _logger.info(
        "github_call",
        extra={
            "gh_method": method,
            "gh_url": redact(url),
            "gh_status": status,
            "gh_latency_ms": latency_ms,
            "gh_outcome": outcome,
        },
    )
