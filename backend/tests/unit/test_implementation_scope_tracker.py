"""Phase 10 scope tracker: touched files outside the plan's allowlist are
flagged (docs/AEGIS_IMPLEMENTATION_PLAN.md Section 18, Absolute Rule 13)."""

from __future__ import annotations

from app.implementation.scope_tracker import unplanned_files
from app.implementation.workspace_rw import clone_rw


def _make_source(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "a.py").write_text("x = 1\n", encoding="utf-8")
    (source / "b.py").write_text("y = 1\n", encoding="utf-8")
    return source


def test_in_scope_edit_is_not_flagged(tmp_path):
    source = _make_source(tmp_path)
    ws = clone_rw("snap-1", source)
    try:
        (ws.root / "a.py").write_text("x = 2\n", encoding="utf-8")
        assert unplanned_files(source, ws, ["a.py"]) == set()
    finally:
        ws.cleanup()


def test_out_of_scope_edit_is_flagged(tmp_path):
    source = _make_source(tmp_path)
    ws = clone_rw("snap-1", source)
    try:
        (ws.root / "a.py").write_text("x = 2\n", encoding="utf-8")
        (ws.root / "b.py").write_text("y = 2\n", encoding="utf-8")
        assert unplanned_files(source, ws, ["a.py"]) == {"b.py"}
    finally:
        ws.cleanup()


def test_new_file_outside_allowlist_is_flagged(tmp_path):
    source = _make_source(tmp_path)
    ws = clone_rw("snap-1", source)
    try:
        (ws.root / "new.py").write_text("z = 1\n", encoding="utf-8")
        assert unplanned_files(source, ws, ["a.py"]) == {"new.py"}
    finally:
        ws.cleanup()
