"""Deterministic failure-type classification (docs/AEGIS_IMPLEMENTATION_PLAN.md
Section 21). Table-driven, no AI: the same inputs always yield the same type.

Types (docs/DATA_MODEL.md Section 2.3 Failure.failure_type):
ASSERTION | EXCEPTION | COLLECTION_ERROR | TIMEOUT | IMPORT_ERROR | ENV
"""

from __future__ import annotations

import re

from app.schemas.failure import FailureType

_ASSERT_MARKER = re.compile(r"(?:^|\n)\s*(?:E\s+)?assert\b", re.IGNORECASE)

_IMPORT_EXCEPTIONS = {"ModuleNotFoundError", "ImportError"}
_COLLECTION_MARKERS = (
    "error collecting",
    "errors during collection",
    "internalerror",
    "conftest.py",
)
_ENV_OUTCOMES = {"OOM", "INFRA_ERROR"}


def classify(
    *,
    exception_type: str | None,
    raw_text: str,
    execution_outcome: str,
) -> FailureType:
    outcome = (execution_outcome or "").upper()
    if outcome == "TIMEOUT":
        return "TIMEOUT"
    if outcome in _ENV_OUTCOMES:
        return "ENV"

    exc = (exception_type or "").strip()
    low = raw_text.lower()

    if exc in _IMPORT_EXCEPTIONS or "modulenotfounderror" in low:
        return "IMPORT_ERROR"
    if any(m in low for m in _COLLECTION_MARKERS):
        return "COLLECTION_ERROR"
    if exc == "AssertionError" or (
        exc in ("", None) and _ASSERT_MARKER.search(raw_text)
    ):
        return "ASSERTION"
    if exc:
        return "EXCEPTION"
    return "ENV"
