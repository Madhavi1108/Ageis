"""Copy-on-write RW workspace. See docs/DECISIONS/ADR-0008 (patch representation)
and docs/AEGIS_IMPLEMENTATION_PLAN.md Phase 10 (Real Patch Generation): the
Implementation agent edits a throwaway copy, never the original snapshot.
"""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from aegis.repository.ingest import Snapshot


@dataclass
class RWWorkspace:
    """A disposable, writable copy of a snapshot's files."""

    snapshot: Snapshot
    root: Path

    def path_for(self, rel_path: str) -> Path:
        return self.root / rel_path

    def cleanup(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def __enter__(self) -> "RWWorkspace":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.cleanup()


def clone_rw(snapshot: Snapshot, *, prefix: str = "aegis-ws-") -> RWWorkspace:
    """Copy every file in the snapshot into a fresh temp directory.

    The original snapshot.root is never touched -- this is the only directory
    the Implementation agent (aegis.implementation.editor) is allowed to write
    into.
    """
    root = Path(tempfile.mkdtemp(prefix=prefix))
    for f in snapshot.files:
        dest = root / f.path
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f.abs_path, dest)
    return RWWorkspace(snapshot=snapshot, root=root)
