"""Phase 10 patcher: ported from tests/unit/test_patcher.py (backend.aegis),
adapted to diff against a real on-disk source workspace directory."""

from __future__ import annotations

from app.implementation.editor import apply_edit_op
from app.implementation.patcher import check_reapplies, touched_paths, unified_diff
from app.implementation.workspace_rw import clone_rw
from app.schemas.implementation import EditOp


def _make_source(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "a.py").write_text("x = 1\n", encoding="utf-8")
    return source


def test_touched_paths_ignores_pytest_cache_and_similar(tmp_path):
    source = _make_source(tmp_path)
    ws = clone_rw("snap-1", source)
    try:
        (ws.root / ".pytest_cache").mkdir()
        (ws.root / ".pytest_cache" / "README.md").write_text("noise", encoding="utf-8")
        (ws.root / ".aegis_report.xml").write_text("<xml/>", encoding="utf-8")
        assert touched_paths(source, ws) == set()
    finally:
        ws.cleanup()


def test_touched_paths_detects_a_real_change(tmp_path):
    source = _make_source(tmp_path)
    ws = clone_rw("snap-1", source)
    try:
        (ws.root / "a.py").write_text("x = 2\n", encoding="utf-8")
        assert touched_paths(source, ws) == {"a.py"}
    finally:
        ws.cleanup()


def test_touched_paths_detects_a_new_file(tmp_path):
    source = _make_source(tmp_path)
    ws = clone_rw("snap-1", source)
    try:
        (ws.root / "new.py").write_text("y = 1\n", encoding="utf-8")
        assert touched_paths(source, ws) == {"new.py"}
    finally:
        ws.cleanup()


def test_unified_diff_nonempty_for_a_real_change(tmp_path):
    source = _make_source(tmp_path)
    ws = clone_rw("snap-1", source)
    try:
        (ws.root / "a.py").write_text("x = 2\n", encoding="utf-8")
        diff = unified_diff(source, ws)
        assert "-x = 1" in diff
        assert "+x = 2" in diff
    finally:
        ws.cleanup()


def test_check_reapplies_true_for_a_reproducible_op(tmp_path):
    source = _make_source(tmp_path)
    ws = clone_rw("snap-1", source)
    try:
        op = EditOp(
            path="a.py",
            op="replace",
            anchor="x = 1",
            new="x = 2",
            plan_step_id="s1",
            rationale="r",
        )
        apply_edit_op(ws, op)
        assert check_reapplies(source, "snap-1", [op], ws) is True
    finally:
        ws.cleanup()


def test_check_reapplies_false_when_ops_dont_match_final_state(tmp_path):
    """The recorded op list must actually explain the final workspace -- if it
    doesn't, reapply must fail, not silently pass."""
    source = _make_source(tmp_path)
    ws = clone_rw("snap-1", source)
    try:
        (ws.root / "a.py").write_text("x = 999\n", encoding="utf-8")
        op = EditOp(
            path="a.py",
            op="replace",
            anchor="x = 1",
            new="x = 2",
            plan_step_id="s1",
            rationale="r",
        )
        assert check_reapplies(source, "snap-1", [op], ws) is False
    finally:
        ws.cleanup()


def test_check_reapplies_false_with_no_ops(tmp_path):
    source = _make_source(tmp_path)
    ws = clone_rw("snap-1", source)
    try:
        assert check_reapplies(source, "snap-1", [], ws) is False
    finally:
        ws.cleanup()
