"""Deterministic failure-type classification."""

from __future__ import annotations

import pytest

from app.debugging.classify import classify


@pytest.mark.parametrize(
    "exc, text, outcome, expected",
    [
        ("AssertionError", "E   assert 1 == 2", "FAIL", "ASSERTION"),
        (None, "E   assert x == y", "FAIL", "ASSERTION"),
        ("ValueError", "E   ValueError: boom", "FAIL", "EXCEPTION"),
        ("ModuleNotFoundError", "No module named 'x'", "ERROR", "IMPORT_ERROR"),
        ("ImportError", "cannot import name", "ERROR", "IMPORT_ERROR"),
        (None, "ERROR collecting test_bad.py", "ERROR", "COLLECTION_ERROR"),
        ("KeyError", "anything", "TIMEOUT", "TIMEOUT"),
        ("KeyError", "anything", "OOM", "ENV"),
        (None, "no markers at all", "FAIL", "ENV"),
    ],
)
def test_classify(exc, text, outcome, expected):
    assert (
        classify(exception_type=exc, raw_text=text, execution_outcome=outcome)
        == expected
    )
