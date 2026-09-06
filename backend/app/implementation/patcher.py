"""Unified diff generation and the patch-reapplies verification check. See
docs/DECISIONS/ADR-0008.

Ported from backend/aegis/implementation/patcher.py: that version diffs
against an in-memory ``Snapshot`` dataclass; this one diffs against the real
on-disk read-only ingestion workspace directory
(app/ingestion/workspace.py::workspace_dir).
"""

from __future__ import annotations

import difflib
from pathlib import Path, PurePosixPath

from app.implementation.editor import EditorError, apply_edit_op
from app.implementation.workspace_rw import RWWorkspace, clone_rw
from app.schemas.implementation import EditOp

# Artifacts a local test run or editor scratch state can leave behind that are
# not part of the actual change and must never be mistaken for a
# touched/unplanned file.
_IGNORED_DIR_NAMES = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".venv",
    "venv",
    "node_modules",
}
_IGNORED_FILE_NAMES = {".aegis_report.xml"}


def _is_ignored(rel_path: str) -> bool:
    p = PurePosixPath(rel_path)
    if p.name in _IGNORED_FILE_NAMES:
        return True
    return any(part in _IGNORED_DIR_NAMES for part in p.parts[:-1])


def _rel_files(root: Path) -> list[str]:
    return sorted(
        p.relative_to(root).as_posix()
        for p in root.rglob("*")
        if p.is_file() and not _is_ignored(p.relative_to(root).as_posix())
    )


def unified_diff(source_workspace: Path, ws: RWWorkspace) -> str:
    """A unified diff of every file in ``ws`` that differs from
    ``source_workspace``, plus any file present in ``ws`` but not in the
    original."""
    chunks: list[str] = []
    ws_paths = _rel_files(ws.root)

    for rel in ws_paths:
        new_text = (ws.root / rel).read_text(encoding="utf-8", errors="replace").splitlines()
        orig_path = source_workspace / rel
        old_text = (
            orig_path.read_text(encoding="utf-8", errors="replace").splitlines()
            if orig_path.is_file()
            else []
        )
        if old_text == new_text:
            continue
        diff = difflib.unified_diff(
            old_text, new_text, fromfile=f"a/{rel}", tofile=f"b/{rel}", lineterm=""
        )
        chunks.append("\n".join(diff))

    return "\n".join(chunks)


def touched_paths(source_workspace: Path, ws: RWWorkspace) -> set[str]:
    """The set of relative paths whose content differs from
    ``source_workspace`` (used by scope_tracker to compare against the plan's
    allowed file set)."""
    touched: set[str] = set()
    for p in ws.root.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(ws.root).as_posix()
        if _is_ignored(rel):
            continue
        orig_path = source_workspace / rel
        if not orig_path.is_file() or orig_path.read_bytes() != p.read_bytes():
            touched.add(rel)
    return touched


def check_reapplies(
    source_workspace: Path,
    snapshot_id: str,
    all_edit_ops: list[EditOp],
    final_ws: RWWorkspace,
) -> bool:
    """Verification criterion ("patch re-applies", Rule 12): independently
    replay every edit-op that produced the final workspace onto a *fresh*
    clone of the original snapshot workspace, and confirm the result matches
    the final workspace byte-for-byte on every touched file.

    This deliberately does not copy bytes from ``final_ws``; it re-derives the
    end state from the original snapshot plus the recorded operations -- the
    change is not an artifact of in-place mutation, it can be regenerated from
    scratch.
    """
    if not all_edit_ops:
        return False  # no recorded change -- nothing to verify as reproducible

    fresh = clone_rw(snapshot_id, source_workspace, prefix="aegis-reapply-check-")
    try:
        for op in all_edit_ops:
            try:
                apply_edit_op(fresh, op)
            except EditorError:
                return False  # the recorded op sequence is not reproducible

        touched = touched_paths(source_workspace, final_ws)
        if not touched:
            return False
        for rel in touched:
            fresh_path = fresh.root / rel
            final_path = final_ws.root / rel
            if not fresh_path.exists() or not final_path.exists():
                return False
            if fresh_path.read_bytes() != final_path.read_bytes():
                return False
        return True
    finally:
        fresh.cleanup()
