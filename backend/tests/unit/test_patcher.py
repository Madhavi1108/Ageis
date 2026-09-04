from aegis.implementation.patcher import check_reapplies, touched_paths, unified_diff
from aegis.repository.ingest import ingest_local
from aegis.repository.workspace import clone_rw
from aegis.schemas.implementation import EditOp


def _make_repo(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    return ingest_local(tmp_path)


def test_touched_paths_ignores_pytest_cache_and_similar(tmp_path):
    snapshot = _make_repo(tmp_path)
    ws = clone_rw(snapshot)
    try:
        (ws.root / ".pytest_cache").mkdir()
        (ws.root / ".pytest_cache" / "README.md").write_text("noise", encoding="utf-8")
        (ws.root / ".aegis_report.xml").write_text("<xml/>", encoding="utf-8")
        assert touched_paths(snapshot, ws) == set()
    finally:
        ws.cleanup()


def test_touched_paths_detects_a_real_change(tmp_path):
    snapshot = _make_repo(tmp_path)
    ws = clone_rw(snapshot)
    try:
        (ws.root / "a.py").write_text("x = 2\n", encoding="utf-8")
        assert touched_paths(snapshot, ws) == {"a.py"}
    finally:
        ws.cleanup()


def test_unified_diff_nonempty_for_a_real_change(tmp_path):
    snapshot = _make_repo(tmp_path)
    ws = clone_rw(snapshot)
    try:
        (ws.root / "a.py").write_text("x = 2\n", encoding="utf-8")
        diff = unified_diff(snapshot, ws)
        assert "-x = 1" in diff
        assert "+x = 2" in diff
    finally:
        ws.cleanup()


def test_check_reapplies_true_for_a_reproducible_op(tmp_path):
    snapshot = _make_repo(tmp_path)
    ws = clone_rw(snapshot)
    try:
        op = EditOp(
            path="a.py",
            op="replace",
            anchor="x = 1",
            new="x = 2",
            plan_step_id="s1",
            rationale="r",
        )
        from aegis.implementation.editor import apply_edit_op

        apply_edit_op(ws, op)
        assert check_reapplies(snapshot, [op], ws) is True
    finally:
        ws.cleanup()


def test_check_reapplies_false_when_ops_dont_match_final_state(tmp_path):
    """The recorded op list must actually explain the final workspace -- if it
    doesn't (e.g. someone tampered with the workspace after the op list was
    captured), reapply must fail, not silently pass."""
    snapshot = _make_repo(tmp_path)
    ws = clone_rw(snapshot)
    try:
        # Apply a DIFFERENT change than the one we'll claim was applied.
        (ws.root / "a.py").write_text("x = 999\n", encoding="utf-8")
        op = EditOp(
            path="a.py",
            op="replace",
            anchor="x = 1",
            new="x = 2",
            plan_step_id="s1",
            rationale="r",
        )
        assert check_reapplies(snapshot, [op], ws) is False
    finally:
        ws.cleanup()


def test_check_reapplies_false_with_no_ops():
    class _Empty:
        files = []

    assert check_reapplies(_Empty(), [], _Empty()) is False  # type: ignore[arg-type]
