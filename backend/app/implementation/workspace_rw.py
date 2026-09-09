"""Copy-on-write RW workspace. See docs/DECISIONS/ADR-0008 (patch representation)
and docs/AEGIS_IMPLEMENTATION_PLAN.md Section 18 (Real Patch Generation): the
Implementation agent edits a throwaway copy, never the read-only ingestion
snapshot workspace (app/ingestion/workspace.py).

Adapted from backend/aegis/repository/workspace.py::clone_rw: that version
copies from an in-memory ``Snapshot`` dataclass; this one copies from the real
on-disk snapshot workspace directory, since app/ingestion/workspace.py already
materializes every ingested snapshot to
``<artifacts_root>/workspaces/<snapshot_id>/`` and marks it read-only.
"""

from __future__ import annotations

import os
import shutil
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path

from app.core.security.pathjail import safe_join


@dataclass
class RWWorkspace:
    """A disposable, writable copy of a snapshot workspace's files."""

    snapshot_id: str
    root: Path

    def path_for(self, rel_path: str) -> Path:
        """Resolve ``rel_path`` inside this workspace.

        ``rel_path`` is frequently untrusted (an AI ``EditOp.path`` /
        ``TestCaseAI.path``, or a path replayed from the DB), so it goes
        through the path jail: an absolute path, a drive/UNC root, ``..``
        traversal, or a symlink escape raises
        :class:`app.core.security.pathjail.PathJailError` (callers translate
        that to their own failure type -- see ``editor.apply_edit_op``).
        """
        return safe_join(self.root, rel_path)

    def cleanup(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def __enter__(self) -> "RWWorkspace":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.cleanup()


def _make_writable(path: Path) -> None:
    """``shutil.copytree`` propagates the source's read-only mode bits
    (app/ingestion/workspace.py::make_read_only marked the source workspace
    read-only) -- undo that on the RW copy so the editor can actually write."""
    for root, dirs, files in os.walk(path):
        for name in files + dirs:
            try:
                os.chmod(Path(root) / name, stat.S_IRWXU)
            except OSError:
                pass
    os.chmod(path, stat.S_IRWXU)


def clone_rw(
    snapshot_id: str, source_workspace: Path, *, prefix: str = "aegis-app-ws-"
) -> RWWorkspace:
    """Copy every file under ``source_workspace`` (the read-only ingestion
    workspace for ``snapshot_id``) into a fresh temp directory.

    ``source_workspace`` is never touched -- this is the only directory the
    Implementation agent (app.implementation.editor) is allowed to write into.
    """
    root = Path(tempfile.mkdtemp(prefix=prefix))
    try:
        shutil.copytree(source_workspace, root, dirs_exist_ok=True)
        _make_writable(root)
    except Exception:
        # Phase 27: callers bind ``ws = clone_rw(...)`` *before* their try/finally,
        # so a mid-copy failure here would leak the mkdtemp'd directory. Clean it
        # up before re-raising.
        shutil.rmtree(root, ignore_errors=True)
        raise
    return RWWorkspace(snapshot_id=snapshot_id, root=root)
