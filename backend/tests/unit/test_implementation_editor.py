"""Phase 10 editor: ported from tests/unit/test_editor.py (backend.aegis),
adapted to app.implementation's real-on-disk-workspace RW clone."""

from __future__ import annotations

import pytest

from app.implementation.editor import (
    AnchorAmbiguousError,
    AnchorNotFoundError,
    EditorError,
    apply_edit_op,
)
from app.implementation.workspace_rw import clone_rw
from app.schemas.implementation import EditOp


@pytest.fixture
def ws(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "a.py").write_text("line one\nline two\nline three\n", encoding="utf-8")
    (source / "dup.py").write_text("same\nsame\n", encoding="utf-8")
    workspace = clone_rw("snap-1", source)
    yield workspace
    workspace.cleanup()


def test_replace_unique_anchor(ws):
    op = EditOp(
        path="a.py",
        op="replace",
        anchor="line two",
        new="LINE TWO",
        plan_step_id="s1",
        rationale="r",
    )
    apply_edit_op(ws, op)
    assert ws.path_for("a.py").read_text() == "line one\nLINE TWO\nline three\n"


def test_missing_anchor_raises(ws):
    op = EditOp(
        path="a.py",
        op="replace",
        anchor="nope",
        new="x",
        plan_step_id="s1",
        rationale="r",
    )
    with pytest.raises(AnchorNotFoundError):
        apply_edit_op(ws, op)


def test_ambiguous_anchor_raises(ws):
    op = EditOp(
        path="dup.py",
        op="replace",
        anchor="same",
        new="x",
        plan_step_id="s1",
        rationale="r",
    )
    with pytest.raises(AnchorAmbiguousError):
        apply_edit_op(ws, op)


def test_insert_before_anchor(ws):
    op = EditOp(
        path="a.py",
        op="insert",
        anchor="line two",
        new="INSERTED\n",
        plan_step_id="s1",
        rationale="r",
    )
    apply_edit_op(ws, op)
    assert (
        ws.path_for("a.py").read_text() == "line one\nINSERTED\nline two\nline three\n"
    )


def test_delete_anchor(ws):
    op = EditOp(
        path="a.py", op="delete", anchor="line two\n", plan_step_id="s1", rationale="r"
    )
    apply_edit_op(ws, op)
    assert ws.path_for("a.py").read_text() == "line one\nline three\n"


def test_create_new_file(ws):
    op = EditOp(
        path="new.py", op="create", new="content\n", plan_step_id="s1", rationale="r"
    )
    apply_edit_op(ws, op)
    assert ws.path_for("new.py").read_text() == "content\n"


def test_edit_nonexistent_file_raises(ws):
    op = EditOp(
        path="missing.py",
        op="replace",
        anchor="x",
        new="y",
        plan_step_id="s1",
        rationale="r",
    )
    with pytest.raises(EditorError):
        apply_edit_op(ws, op)


def test_empty_anchor_raises(ws):
    op = EditOp(
        path="a.py", op="replace", anchor="", new="y", plan_step_id="s1", rationale="r"
    )
    with pytest.raises(EditorError):
        apply_edit_op(ws, op)


def test_rw_workspace_writable_even_when_source_is_read_only(tmp_path):
    """The RW clone must be writable even though the ingestion snapshot
    workspace it's copied from is chmod'd read-only (app/ingestion/workspace.py
    ::make_read_only) -- shutil.copytree otherwise propagates that mode."""
    from app.ingestion.workspace import make_read_only

    source = tmp_path / "source"
    source.mkdir()
    (source / "a.py").write_text("x = 1\n", encoding="utf-8")
    make_read_only(source)

    ws = clone_rw("snap-1", source)
    try:
        op = EditOp(
            path="a.py", op="replace", anchor="x = 1", new="x = 2",
            plan_step_id="s1", rationale="r",
        )
        apply_edit_op(ws, op)
        assert ws.path_for("a.py").read_text() == "x = 2\n"
    finally:
        ws.cleanup()
        from app.ingestion.workspace import cleanup

        cleanup(source)
