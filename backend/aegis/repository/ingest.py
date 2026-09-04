"""Reduced repository ingestion -- local path only.

Full design: docs/REPOSITORY_ANALYSIS.md Section 1, docs/DECISIONS/ADR-0006.
This is the Phase 1 "just enough" slice of Phase 3 (Repository Ingestion):
local paths only (no GitHub URLs, no SSRF surface to guard), no Git history,
no size/history limits -- those are Phase 3's job. What is real here: path
containment, a manifest with hashes, and language/test detection.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

_IGNORED_DIR_NAMES = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".venv",
    "venv",
    "node_modules",
}


@dataclass(frozen=True)
class RepositoryFile:
    path: str  # relative, POSIX-style
    abs_path: Path
    size_bytes: int
    sha256: str
    language: str
    is_test: bool


@dataclass(frozen=True)
class Snapshot:
    """An immutable-in-spirit view of a local repository (Phase 1 reduction of
    docs/DATA_MODEL.md's RepositorySnapshot -- no DB row, no commit sha)."""

    root: Path
    files: list[RepositoryFile] = field(default_factory=list)

    def file_by_path(self, rel_path: str) -> RepositoryFile | None:
        for f in self.files:
            if f.path == rel_path:
                return f
        return None

    def python_files(self) -> list[RepositoryFile]:
        return [f for f in self.files if f.language == "python"]


class IngestError(ValueError):
    """Raised for an invalid or inaccessible local repository path."""


def _detect_language(path: Path) -> str:
    if path.suffix == ".py":
        return "python"
    if path.suffix == ".md":
        return "markdown"
    return "other"


def _is_test_file(rel_path: str) -> bool:
    name = Path(rel_path).name
    return name.startswith("test_") or name.endswith("_test.py")


def ingest_local(repo_path: str | Path) -> Snapshot:
    """Ingest a local directory. Raises IngestError for anything invalid.

    No repository code is ever executed here -- only read and hashed.
    """
    root = Path(repo_path).resolve()
    if not root.exists():
        raise IngestError(f"repository path does not exist: {root}")
    if not root.is_dir():
        raise IngestError(f"repository path is not a directory: {root}")

    files: list[RepositoryFile] = []
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        if any(part in _IGNORED_DIR_NAMES for part in p.relative_to(root).parts):
            continue
        rel = p.relative_to(root).as_posix()
        data = p.read_bytes()
        files.append(
            RepositoryFile(
                path=rel,
                abs_path=p,
                size_bytes=len(data),
                sha256=hashlib.sha256(data).hexdigest(),
                language=_detect_language(p),
                is_test=_is_test_file(rel),
            )
        )
    return Snapshot(root=root, files=files)
