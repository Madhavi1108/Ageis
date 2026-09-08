"""Workspace path jail (docs/SECURITY_MODEL.md Section 2 "filesystem escape").

``RWWorkspace.path_for`` now runs ``core.security.pathjail.safe_join``; an
AI-controlled ``EditOp.path`` / ``TestCaseAI.path`` that escapes the workspace
is turned into a recorded ``EditorError`` (a failed attempt), never a write.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.security.pathjail import PathJailError, safe_join
from app.implementation.editor import EditorError, apply_edit_op
from app.implementation.workspace_rw import RWWorkspace
from app.schemas.implementation import EditOp


@pytest.fixture
def ws(tmp_path) -> RWWorkspace:
    root = tmp_path / "ws"
    root.mkdir()
    (root / "keep.py").write_text("x = 1\n", encoding="utf-8")
    return RWWorkspace(snapshot_id="s1", root=root)


ESCAPES = [
    "../evil.py",
    "../../evil.py",
    "a/../../evil.py",
    "/etc/passwd",
    "\\\\host\\share\\x",
    "C:\\Windows\\system32\\x",
    "C:relative",
    "foo/../../bar",
    "",
    "   ",
]


@pytest.mark.parametrize("rel", ESCAPES)
def test_safe_join_rejects_escapes(tmp_path, rel):
    with pytest.raises(PathJailError):
        safe_join(tmp_path, rel)


@pytest.mark.parametrize("rel", ["a.py", "pkg/mod.py", "a/b/c/d.py", "./x.py"])
def test_safe_join_allows_contained_paths(tmp_path, rel):
    out = safe_join(tmp_path, rel)
    assert str(out).startswith(str(tmp_path.resolve()))


def test_safe_join_rejects_symlink_escape(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        (root / "link").symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not permitted on this host")
    with pytest.raises(PathJailError):
        safe_join(root, "link/pwned.py")


def test_editor_create_outside_workspace_is_an_editor_error(ws):
    op = EditOp(
        path="../../pwned.py",
        op="create",
        new="print('pwned')",
        plan_step_id="s1",
        rationale="malicious",
    )
    with pytest.raises(EditorError):
        apply_edit_op(ws, op)
    assert not (ws.root.parent.parent / "pwned.py").exists()
    assert not (Path(ws.root).parent / "pwned.py").exists()


def test_editor_absolute_path_is_an_editor_error(ws, tmp_path):
    victim = tmp_path / "victim.py"
    op = EditOp(
        path=str(victim),
        op="create",
        new="0",
        plan_step_id="s1",
        rationale="malicious",
    )
    with pytest.raises(EditorError):
        apply_edit_op(ws, op)
    assert not victim.exists()


def test_path_for_still_serves_legitimate_paths(ws):
    assert ws.path_for("keep.py").read_text() == "x = 1\n"
