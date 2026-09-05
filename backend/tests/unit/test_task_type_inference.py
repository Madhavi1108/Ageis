"""Unit tests for app/services/tasks.py::infer_task_type -- deterministic rules
and their documented precedence (docs/AEGIS_IMPLEMENTATION_PLAN.md Section 14).
"""

from __future__ import annotations

import pytest

from app.services.tasks import infer_task_type

CASES = [
    # (title, description, expected)
    ("Fix incorrect total when discount exceeds the max", "", "BUG"),
    ("App crashes on startup", "traceback attached", "BUG"),
    ("Checkout returns the wrong price", "it should not double-charge", "BUG"),
    ("Add a dark-mode toggle", "users want it", "FEATURE"),
    ("Implement CSV export", "", "FEATURE"),
    ("Support webhooks for task completion", "", "FEATURE"),
    ("Refactor the invoice module", "split calculate_total into helpers", "REFACTOR"),
    ("Rename calculate_total to compute_total", "", "REFACTOR"),
    ("Clean up dead code in utils", "", "REFACTOR"),
    ("How do I configure the sandbox timeout?", "", "QUESTION"),
    ("Is it possible to run without Docker?", "", "QUESTION"),
    ("Why does analysis skip vendored files", "", "QUESTION"),
    ("Invoices must round to two decimal places", "regulatory requirement", "REQUIREMENT"),
    ("The system tracks per-tenant usage quotas", "", "REQUIREMENT"),
]


@pytest.mark.parametrize("title,description,expected", CASES)
def test_infer_task_type(title, description, expected):
    assert infer_task_type(title, description) == expected


def test_question_precedence_beats_bug_keyword():
    # Contains "fix" (a BUG marker) but is phrased as a question.
    assert infer_task_type("How do I fix the flaky test?", "") == "QUESTION"


def test_refactor_precedence_beats_bug_keyword():
    # "broken" is a BUG marker, but an explicit refactor ask wins.
    assert (
        infer_task_type("Refactor broken retry logic", "tech debt cleanup")
        == "REFACTOR"
    )


def test_bug_precedence_beats_feature_keyword():
    # "add" is a FEATURE marker; the bug framing wins.
    assert (
        infer_task_type(
            "Fix wrong rounding", "also add a regression test for the boundary"
        )
        == "BUG"
    )


def test_default_is_requirement():
    assert infer_task_type("Persist audit records for seven years", "") == "REQUIREMENT"
