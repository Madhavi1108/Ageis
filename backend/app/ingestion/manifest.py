"""Manifest building: deterministic file walk + hashing + language/vendored/test detection.

Extends backend/aegis/repository/ingest.py's Phase 1 heuristics (ignored-dir-names,
naive extension table, is_test) with a fuller language table, shebang fallback, and
is_vendored detection. No .gitignore parsing -- heuristic directory-name lists only,
matching the Phase 3 plan's stated manifest scope.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

_IGNORED_DIR_NAMES = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".venv",
    "venv",
    "node_modules",
}
_VENDORED_DIR_NAMES = {
    "vendor",
    "vendored",
    "third_party",
    "node_modules",
    "site-packages",
    "dist",
    "build",
}

_LANGUAGE_BY_EXTENSION = {
    ".py": "python",
    ".md": "markdown",
    ".rst": "text",
    ".txt": "text",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".cfg": "ini",
    ".ini": "ini",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".sh": "shell",
    ".bash": "shell",
    ".html": "html",
    ".css": "css",
    ".sql": "sql",
    ".dockerfile": "dockerfile",
}

_SHEBANG_LANGUAGE = {
    "python": "python",
    "python3": "python",
    "bash": "shell",
    "sh": "shell",
    "node": "javascript",
}


@dataclass(frozen=True)
class ManifestFile:
    path: str
    size_bytes: int
    sha256: str
    language: str
    is_test: bool
    is_vendored: bool
    parse_status: str = "OK"
    parse_error: str | None = None


def is_vendored(rel_path: str) -> bool:
    return any(part in _VENDORED_DIR_NAMES for part in Path(rel_path).parts[:-1])


def _is_test_file(name: str) -> bool:
    return name.startswith("test_") or name.endswith("_test.py")


def _detect_shebang_language(abs_path: Path) -> str | None:
    try:
        with abs_path.open("rb") as fh:
            head = fh.read(256)
    except OSError:
        return None
    if b"\x00" in head:
        return None  # binary
    if not head.startswith(b"#!"):
        return None
    first_line = head.split(b"\n", 1)[0].decode("utf-8", errors="ignore")
    for token, language in _SHEBANG_LANGUAGE.items():
        if token in first_line:
            return language
    return None


def detect_language(abs_path: Path) -> str:
    ext = abs_path.suffix.lower()
    if ext in _LANGUAGE_BY_EXTENSION:
        return _LANGUAGE_BY_EXTENSION[ext]
    shebang_language = _detect_shebang_language(abs_path)
    if shebang_language:
        return shebang_language
    return "other"


def build_manifest(root: Path) -> list[ManifestFile]:
    """Walk `root` deterministically (sorted), skip ignored dirs, hash every file.
    Never executes anything under `root`."""
    files: list[ManifestFile] = []
    for path in sorted(root.rglob("*")):
        if path.is_dir():
            continue
        if any(
            part in _IGNORED_DIR_NAMES for part in path.relative_to(root).parts[:-1]
        ):
            continue
        rel_path = path.relative_to(root).as_posix()
        data = path.read_bytes()
        files.append(
            ManifestFile(
                path=rel_path,
                size_bytes=len(data),
                sha256=hashlib.sha256(data).hexdigest(),
                language=detect_language(path),
                is_test=_is_test_file(path.name),
                is_vendored=is_vendored(rel_path),
            )
        )
    return files
