import pytest

from aegis.implementation.editor import (
    AnchorAmbiguousError,
    AnchorNotFoundError,
    EditorError,
    apply_edit_op,
)
from aegis.repository.ingest import ingest_local
from aegis.repository.workspace import clone_rw
from aegis.schemas.implementation import EditOp


@pytest.fixture
def ws(tmp_path):
    (tmp_path / "a.py").write_text("line one\nline two\nline three\n", encoding="utf-8")
    (tmp_path / "dup.py").write_text("same\nsame\n", encoding="utf-8")
    snapshot = ingest_local(tmp_path)
    workspace = clone_rw(snapshot)
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
