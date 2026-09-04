"""Unified diff generation and the patch-reapplies verification check. See
docs/DECISIONS/ADR-0008.
"""

from __future__ import annotations

import difflib

from aegis.implementation.editor import EditorError, apply_edit_op
from aegis.repository.ingest import Snapshot
from aegis.repository.workspace import RWWorkspace, clone_rw
from aegis.schemas.implementation import EditOp

# Artifacts a local test run (FakeSandboxRunner, or pytest's own cache) can
# leave behind in the workspace that are not part of the actual change and
# must never be mistaken for a touched/unplanned file.
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
    from pathlib import PurePosixPath

    p = PurePosixPath(rel_path)
    if p.name in _IGNORED_FILE_NAMES:
        return True
    return any(part in _IGNORED_DIR_NAMES for part in p.parts[:-1])


def unified_diff(snapshot: Snapshot, ws: RWWorkspace) -> str:
    """A unified diff of every file in `ws` that differs from `snapshot`,
    plus any file present in `ws` but not in the original snapshot."""
    chunks: list[str] = []
    original_by_path = {f.path: f for f in snapshot.files}
    ws_paths = sorted(
        p.relative_to(ws.root).as_posix()
        for p in ws.root.rglob("*")
        if p.is_file() and not _is_ignored(p.relative_to(ws.root).as_posix())
    )

    for rel in ws_paths:
        new_text = (
            (ws.root / rel).read_text(encoding="utf-8", errors="replace").splitlines()
        )
        orig_file = original_by_path.get(rel)
        old_text = (
            orig_file.abs_path.read_text(
                encoding="utf-8", errors="replace"
            ).splitlines()
            if orig_file
            else []
        )
        if old_text == new_text:
            continue
        diff = difflib.unified_diff(
            old_text, new_text, fromfile=f"a/{rel}", tofile=f"b/{rel}", lineterm=""
        )
        chunks.append("\n".join(diff))

    return "\n".join(chunks)


def touched_paths(snapshot: Snapshot, ws: RWWorkspace) -> set[str]:
    """The set of relative paths whose content differs from the snapshot
    (used by scope_tracker to compare against the plan's allowed file set)."""
    original_by_path = {f.path: f for f in snapshot.files}
    touched: set[str] = set()
    for p in ws.root.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(ws.root).as_posix()
        if _is_ignored(rel):
            continue
        new_bytes = p.read_bytes()
        orig = original_by_path.get(rel)
        if orig is None or orig.abs_path.read_bytes() != new_bytes:
            touched.add(rel)
    return touched


def check_reapplies(
    snapshot: Snapshot, all_edit_ops: list[EditOp], final_ws: RWWorkspace
) -> bool:
    """Verification criterion 3 ("patch re-applies"): independently replay
    every edit-op that produced the final workspace -- initial implementation
    plus any repair attempts, in order -- onto a *fresh* clone of the
    original snapshot, and confirm the result matches the final workspace
    byte-for-byte on every touched file.

    This deliberately does not copy bytes from `final_ws`; it re-derives the
    end state from the original snapshot plus the recorded operations, which
    is what "reversible and reproducible" (Specification Rule 12) actually
    means: the change is not an artifact of in-place mutation, it can be
    regenerated from scratch.
    """
    if not all_edit_ops:
        return False  # no recorded change -- nothing to verify as reproducible

    fresh = clone_rw(snapshot, prefix="aegis-reapply-check-")
    try:
        for op in all_edit_ops:
            try:
                apply_edit_op(fresh, op)
            except EditorError:
                return False  # the recorded op sequence is not reproducible

        touched = touched_paths(snapshot, final_ws)
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
