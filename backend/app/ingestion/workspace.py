"""Ingestion workspace materialization: build, mark read-only, clean up.

Layout: <settings.artifacts_root>/workspaces/<snapshot_id>/ (docs/DATA_MODEL.md Section 4).
This is the read-only ingestion snapshot workspace -- distinct from the Implementation
agent's copy-on-write RW workspace (backend/aegis/repository/workspace.py::clone_rw and
its Phase 3+ successor), which is always a *separate* directory. No code path in this
codebase ever writes back into a snapshot workspace after make_read_only() runs.
"""

from __future__ import annotations

import os
import shutil
import stat
import sys
from pathlib import Path

from app.core.config import Settings


def workspace_dir(snapshot_id: str, settings: Settings) -> Path:
    return Path(settings.artifacts_root) / "workspaces" / snapshot_id


def materialize_from_clone(cloned_repo_root: Path, dest: Path) -> None:
    """Move the already-cloned tree into `dest`, dropping .git -- commit_sha/branch/
    history_depth are already captured as manifest metadata before this is called."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        cleanup(dest)
    shutil.move(str(cloned_repo_root), str(dest))
    git_dir = dest / ".git"
    if git_dir.exists():
        shutil.rmtree(git_dir, ignore_errors=True)


def materialize_from_local(source_root: Path, dest: Path) -> None:
    """Copy `source_root` into `dest` -- never move/mutate the user's own working tree."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        cleanup(dest)
    shutil.copytree(
        source_root,
        dest,
        ignore=shutil.ignore_patterns(
            ".git", "__pycache__", ".pytest_cache", ".venv", "venv"
        ),
    )


def make_read_only(path: Path) -> None:
    """Best-effort read-only marking.

    On POSIX (Linux/macOS -- including CI) this is a real security boundary:
    os.chmod clears the write bits for owner/group/other. On Windows dev, chmod only
    toggles the basic read-only *attribute* (NTFS ACLs are the real permission model,
    not POSIX mode bits) -- this is intentionally NOT a hard boundary there. The actual
    containment guarantee is architectural: no code in this codebase ever writes into a
    snapshot workspace after this call; edits always happen in a separate RW workspace.
    """
    for root, dirs, files in os.walk(path):
        for name in files:
            file_path = Path(root) / name
            if sys.platform == "win32":
                os.chmod(file_path, stat.S_IREAD)
            else:
                os.chmod(file_path, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        for name in dirs:
            dir_path = Path(root) / name
            if sys.platform != "win32":
                os.chmod(
                    dir_path, stat.S_IRUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP
                )
    if sys.platform != "win32":
        os.chmod(path, stat.S_IRUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP)


def _restore_writable(path: Path) -> None:
    for root, dirs, files in os.walk(path):
        for name in dirs + files:
            try:
                os.chmod(Path(root) / name, stat.S_IRWXU)
            except OSError:
                pass
    try:
        os.chmod(path, stat.S_IRWXU)
    except OSError:
        pass


def cleanup(path: Path) -> None:
    """Remove a workspace directory, including one previously made read-only by
    make_read_only() (read-only dirs can't have files unlinked from them on POSIX
    without first restoring the write bit)."""
    if path.exists():
        _restore_writable(path)
    shutil.rmtree(path, ignore_errors=True)
