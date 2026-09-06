"""Redacted AI request logging: digest, never the raw prompt or a secret."""

from __future__ import annotations

import json
import logging

from app.ai.request_log import log_ai_call, prompt_digest


def test_digest_is_stable_and_non_reversible():
    d1 = prompt_digest("hello world")
    d2 = prompt_digest("hello world")
    assert d1 == d2 and d1.startswith("sha256:")
    assert "hello world" not in d1


class _Capture(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.INFO)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def test_log_record_has_metadata_and_no_raw_prompt():
    # Attach our own handler straight to the "app.ai" logger -- immune to
    # whatever global logging config other tests / app import left behind.
    logger = logging.getLogger("app.ai")
    handler = _Capture()
    prev_level, prev_propagate = logger.level, logger.propagate
    prev_disabled = logger.disabled
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    # alembic's fileConfig (run by test_migrations) sets
    # disable_existing_loggers=True, which leaves this logger disabled for the
    # rest of the session -- re-enable it for the assertion.
    logger.disabled = False
    secret_prompt = (
        "The user's issue text: fix the bug. api_key=sk-abcdef0123456789abcdef"
    )
    try:
        log_ai_call(
            provider="mock",
            model="mock",
            template="planning",
            tier="frontier",
            latency_ms=12,
            prompt=secret_prompt,
            outcome="ok",
        )
    finally:
        logger.removeHandler(handler)
        logger.setLevel(prev_level)
        logger.propagate = prev_propagate
        logger.disabled = prev_disabled

    rec = next(r for r in handler.records if r.getMessage() == "ai_call")
    assert rec.ai_provider == "mock"
    assert rec.ai_tier == "frontier"
    assert rec.ai_prompt_digest.startswith("sha256:")
    assert rec.ai_prompt_chars == len(secret_prompt)

    blob = json.dumps(
        {k: v for k, v in rec.__dict__.items() if not k.startswith("_")}, default=str
    )
    assert "fix the bug" not in blob
    assert "sk-abcdef" not in blob
