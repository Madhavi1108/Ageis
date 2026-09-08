"""Workspace path jail (docs/SECURITY_MODEL.md Section 2 "filesystem escape /
path traversal", ADR-0011).

Every filesystem operation that joins an *externally influenced* relative path
(an AI ``EditOp.path`` / ``TestCaseAI.path``, a path replayed from the DB, a
path walked out of a repo) to a base directory must go through :func:`safe_join`.
It resolves the result and asserts it stays inside the base -- rejecting
absolute paths, Windows drive letters / UNC roots, ``..`` traversal, and
symlink components that would hop outside.

This is the host-side counterpart to the sandbox's ``--read-only`` rootfs: the
AI only ever gets to touch files under the throwaway RW workspace.
"""

from __future__ import annotations

import os
from pathlib import Path, PurePosixPath, PureWindowsPath


class PathJailError(Exception):
    """A relative path escaped (or tried to escape) its workspace root."""


def _looks_absolute(rel: str) -> bool:
    # Catch POSIX-absolute, Windows drive-absolute (``C:\``), UNC (``\\host``),
    # and drive-relative (``C:foo``) before they ever reach ``Path`` joining,
    # where semantics differ by host OS.
    if not rel:
        return False
    if rel[0] in ("/", "\\"):
        return True
    if PureWindowsPath(rel).drive or PureWindowsPath(rel).is_absolute():
        return True
    if PurePosixPath(rel).is_absolute():
        return True
    return False


def safe_join(root: Path, rel: str) -> Path:
    """Return ``root / rel`` guaranteed to sit inside ``root``.

    Raises :class:`PathJailError` on an absolute path, a drive/UNC root, any
    ``..`` component, or a resolved target outside ``root`` (including via a
    symlink).
    """
    if not isinstance(rel, str) or not rel.strip():
        raise PathJailError(f"empty or non-string workspace path: {rel!r}")

    if _looks_absolute(rel):
        raise PathJailError(f"absolute paths are not allowed in the workspace: {rel!r}")

    # Normalise separators, then reject any parent-dir hop by component -- do
    # this on the *lexical* path before touching the filesystem.
    parts = PurePosixPath(rel.replace("\\", "/")).parts
    if any(p == ".." for p in parts):
        raise PathJailError(f"'..' is not allowed in a workspace path: {rel!r}")

    root_resolved = root.resolve()
    target = (root_resolved / PurePosixPath(rel.replace("\\", "/"))).resolve()

    # ``Path.resolve`` follows symlinks; ``is_relative_to`` (3.9+) is the
    # containment assertion. ``os.path.commonpath`` guards the pre-3.12 quirk
    # where ``resolve`` on a non-existent path can differ subtly across OSes.
    try:
        inside = target == root_resolved or target.is_relative_to(root_resolved)
    except ValueError:  # different drives on Windows
        inside = False
    if not inside:
        raise PathJailError(
            f"workspace path {rel!r} resolves to {target}, outside {root_resolved}"
        )

    # Belt-and-braces for exotic cases (case-folding filesystems, ``\\?\`` etc.).
    if os.path.commonpath([str(root_resolved), str(target)]) != str(root_resolved):
        raise PathJailError(
            f"workspace path {rel!r} escapes {root_resolved} (commonpath check)"
        )
    return target
