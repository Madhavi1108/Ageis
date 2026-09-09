"""Phase 27 unit: deterministic AI-context windowing (app/ai/context.py)."""

from __future__ import annotations

from app.ai.context import (
    DROPPED_PLACEHOLDER,
    ContextSection,
    estimate_tokens,
    fit_context,
)


def _sections():
    return [
        ContextSection("task", "T" * 400, priority=0),
        ContextSection("impact", "I" * 400, priority=3),
        ContextSection("memory", "M" * 400, priority=5),
        ContextSection("files", "F" * 400, priority=2),
    ]


def test_under_budget_keeps_everything_unchanged():
    res = fit_context(_sections(), budget_tokens=10_000)
    assert not res.changed
    assert res.dropped == [] and res.truncated == []
    assert res.kept["memory"] == "M" * 400
    assert res.note() == ""


def test_over_budget_drops_lowest_priority_first():
    # total ~= 4 * 100 = 400 tokens; budget forces dropping the two least
    # important whole sections (memory p5, then impact p3) before files (p2).
    res = fit_context(_sections(), budget_tokens=210)
    assert "memory" in res.dropped
    assert res.dropped.index("memory") == 0  # least important goes first
    assert res.kept["memory"] == DROPPED_PLACEHOLDER
    assert "task" not in res.dropped  # priority 0 is untouchable
    assert res.kept["task"] == "T" * 400


def test_priority_zero_never_dropped_or_truncated_even_if_alone_over_budget():
    res = fit_context([ContextSection("task", "T" * 4000, priority=0)], budget_tokens=1)
    assert res.dropped == [] and res.truncated == []
    assert res.kept["task"] == "T" * 4000


def test_droppable_section_removed_when_priority_zero_dominates_budget():
    res = fit_context(
        [
            ContextSection("task", "T" * 40, priority=0),
            ContextSection("big", "B" * 4000, priority=2),
        ],
        budget_tokens=60,
    )
    # can't touch task (p0); big is dropped whole and recorded as provenance.
    assert res.changed
    assert "big" in res.dropped
    assert res.kept["task"] == "T" * 40


def test_deterministic_same_inputs_same_output():
    a = fit_context(_sections(), budget_tokens=180)
    b = fit_context(_sections(), budget_tokens=180)
    assert (a.dropped, a.truncated, a.kept) == (b.dropped, b.truncated, b.kept)


def test_kept_has_an_entry_for_every_input_section():
    res = fit_context(_sections(), budget_tokens=1)
    assert set(res.kept) == {"task", "impact", "memory", "files"}


def test_note_is_a_provenance_string_when_changed():
    res = fit_context(_sections(), budget_tokens=180)
    assert res.changed
    note = res.note()
    assert "omitted" in note or "truncated" in note


def test_estimate_tokens():
    assert estimate_tokens("") == 0
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("abcde") == 2  # ceil(5/4)
