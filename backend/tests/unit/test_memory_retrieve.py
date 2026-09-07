"""Phase 20 unit: MemoryHit ranking -- same-repo boost, symbol overlap,
recency, exclusion, the min-similarity floor, and the mandatory label.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.core.config import Settings
from app.memory import MEMORY_LABEL
from app.memory.retrieve import retrieve

_SETTINGS = Settings(_env_file=None, memory_enabled=True)


def _row(task_id, *, repo="repo-1", days_old=1.0, symbols=None, files=None, text="", fix=""):
    return SimpleNamespace(
        task_id=task_id,
        repository_id=repo,
        outcome="VERIFIED",
        verification_verdict="VERIFIED",
        issue_text_sanitized=text,
        fix_summary=fix,
        touched_symbols=symbols or [],
        touched_files=files or [],
        created_at=datetime.now(timezone.utc) - timedelta(days=days_old),
    )


def test_same_repo_boost_lifts_an_equal_hit():
    rows = [
        _row("same", repo="repo-1", text="discount cap invoice", files=["invoice.py"]),
        _row("other", repo="repo-2", text="discount cap invoice", files=["invoice.py"]),
    ]
    hits = retrieve(
        rows,
        query_text="discount cap invoice",
        repository_id="repo-1",
        exclude_task_id=None,
        settings=_SETTINGS,
    )
    assert [h.task_id for h in hits][0] == "same"
    assert hits[0].same_repository is True
    assert hits[0].similarity > next(h for h in hits if h.task_id == "other").similarity


def test_symbol_overlap_moves_rank():
    rows = [
        _row("with_sym", text="totals", symbols=["invoice.py::calculate_total"], files=["invoice.py"]),
        _row("no_sym", text="totals", symbols=[], files=["invoice.py"]),
    ]
    hits = retrieve(
        rows,
        query_text="fix invoice.py::calculate_total discount",
        repository_id="repo-1",
        exclude_task_id=None,
        settings=_SETTINGS,
    )
    assert hits[0].task_id == "with_sym"


def test_recency_breaks_an_otherwise_tie():
    rows = [
        _row("fresh", days_old=1, text="discount cap", files=["invoice.py"]),
        _row("stale", days_old=400, text="discount cap", files=["invoice.py"]),
    ]
    hits = retrieve(
        rows, query_text="discount cap", repository_id="repo-1",
        exclude_task_id=None, settings=_SETTINGS,
    )
    assert hits[0].task_id == "fresh"


def test_exclude_task_and_min_similarity_and_label():
    rows = [
        _row("self", text="discount cap invoice"),
        _row("unrelated", text="something entirely different xyzzy"),
    ]
    hits = retrieve(
        rows, query_text="discount cap invoice", repository_id="repo-1",
        exclude_task_id="self", settings=_SETTINGS,
    )
    assert "self" not in {h.task_id for h in hits}
    # 'unrelated' has ~no lexical overlap; recency-only score is below the floor
    assert "unrelated" not in {h.task_id for h in hits}
    for h in hits:
        assert h.label == MEMORY_LABEL
        assert h.provenance.startswith("task ")


def test_empty_rows_returns_empty():
    assert retrieve([], query_text="x", repository_id="r", exclude_task_id=None, settings=_SETTINGS) == []
