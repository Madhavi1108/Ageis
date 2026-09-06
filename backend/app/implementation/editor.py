"""Anchored edit application. See docs/DECISIONS/ADR-0008: the AI proposes
structured edit operations, never a whole-file rewrite; an ambiguous or
missing anchor stops loudly rather than guessing.

Ported from backend/aegis/implementation/editor.py.
"""

from __future__ import annotations

from app.implementation.workspace_rw import RWWorkspace
from app.schemas.implementation import EditOp


class EditorError(Exception):
    """Base class for anchor/apply failures. Callers (the implementation
    service) must catch this and record a failed attempt -- never crash the
    pipeline on a bad edit-op (no fake functionality, but also no exceptions
    leaking past agent boundaries)."""


class AnchorNotFoundError(EditorError):
    pass


class AnchorAmbiguousError(EditorError):
    pass


def apply_edit_op(ws: RWWorkspace, op: EditOp) -> None:
    """Apply one EditOp to the workspace. Raises EditorError subclasses on
    an anchor problem; the caller decides what to do next."""
    target = ws.path_for(op.path)

    if op.op == "create":
        if op.new is None:
            raise EditorError(f"create op for {op.path!r} has no `new` content")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(op.new, encoding="utf-8")
        return

    if not target.exists():
        raise EditorError(f"cannot {op.op} nonexistent file {op.path!r}")

    text = target.read_text(encoding="utf-8")
    if not op.anchor:
        raise EditorError(f"{op.op} op for {op.path!r} requires a non-empty anchor")

    count = text.count(op.anchor)
    if count == 0:
        raise AnchorNotFoundError(f"anchor not found in {op.path!r}: {op.anchor!r}")
    if count > 1:
        raise AnchorAmbiguousError(
            f"anchor matches {count} times in {op.path!r} (must be unique): {op.anchor!r}"
        )

    if op.op == "replace":
        if op.new is None:
            raise EditorError(f"replace op for {op.path!r} has no `new` content")
        text = text.replace(op.anchor, op.new, 1)
    elif op.op == "insert":
        if op.new is None:
            raise EditorError(f"insert op for {op.path!r} has no `new` content")
        text = text.replace(op.anchor, op.new + op.anchor, 1)
    elif op.op == "delete":
        text = text.replace(op.anchor, "", 1)
    else:
        raise EditorError(f"unknown op {op.op!r}")

    target.write_text(text, encoding="utf-8")


def apply_edit_ops(ws: RWWorkspace, ops: list[EditOp]) -> list[str]:
    """Apply every op in order. Returns the list of touched relative paths.
    Raises on the first EditorError -- callers wrap this per attempt."""
    touched: list[str] = []
    for op in ops:
        apply_edit_op(ws, op)
        touched.append(op.path)
    return touched
