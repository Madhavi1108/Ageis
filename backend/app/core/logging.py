"""Structured JSON logging with secret redaction.

See docs/AEGIS_IMPLEMENTATION_PLAN.md Section 10: "JSON logging with a
correlation/task id and a redaction filter for known secret patterns."
"""

from __future__ import annotations

import json
import logging
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

from app.core.config import Settings
from app.core.security import redact

correlation_id_var: ContextVar[str | None] = ContextVar("correlation_id", default=None)

_RESERVED_RECORD_ATTRS = frozenset(
    logging.LogRecord("", 0, "", 0, "", (), None).__dict__
)


class RedactionFilter(logging.Filter):
    """Masks secret-shaped substrings in a record's message and args before formatting."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(str(record.getMessage()))
        record.args = ()
        return True


class JSONFormatter(logging.Formatter):
    """Renders each log record as one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": correlation_id_var.get(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED_RECORD_ATTRS and key not in payload:
                payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return redact(json.dumps(payload, default=str))


def configure_logging(settings: Settings) -> None:
    """Install JSON logging + redaction on the root logger. Idempotent."""
    root = logging.getLogger()
    root.setLevel(settings.log_level)
    root.handlers.clear()

    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    handler.addFilter(RedactionFilter())
    root.addHandler(handler)
