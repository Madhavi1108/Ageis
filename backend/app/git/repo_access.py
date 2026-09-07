"""Reach a real Git repository for a snapshot (ADR-0014).

The materialized snapshot workspace has no ``.git`` (app/ingestion/workspace.py
strips it), so history/blame/churn run against the repo another way:

* ``LOCAL``  -- open ``repository.url_or_path`` if it is itself a Git work tree.
* ``GITHUB`` -- a fresh shallow re-clone into a temp dir (cleaned up by the
  caller via ``handle.cleanup()``).
* a ``"local:"`` pseudo-sha snapshot, or a plain files-only directory -- no Git
  history is reachable; ``open_repo`` returns ``None`` and callers report a
  structured "unavailable" result.
"""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from app.ingestion.git_client import clone_shallow, open_local
from app.ingestion.url_validator import validate_remote_url


@dataclass
class GitRepoHandle:
    repo: object  # git.Repo
    cleanup: Callable[[], None]
    source: str  # "local" | "clone"

    def __enter__(self) -> "GitRepoHandle":
        return self

    def __exit__(self, *exc: object) -> None:
        self.cleanup()


def open_repo(repository, snapshot, settings) -> GitRepoHandle | None:
    if snapshot is not None and str(snapshot.commit_sha or "").startswith("local:"):
        return None

    if repository.source_type == "LOCAL":
        repo = open_local(Path(repository.url_or_path))
        if repo is None:
            return None
        return GitRepoHandle(repo=repo, cleanup=lambda: None, source="local")

    if repository.source_type == "GITHUB":
        parsed = validate_remote_url(repository.url_or_path, settings)
        tmp = Path(tempfile.mkdtemp(prefix="aegis-git-intel-"))

        def _cleanup() -> None:
            shutil.rmtree(tmp, ignore_errors=True)

        try:
            repo = clone_shallow(
                parsed.clone_url,
                tmp,
                depth=settings.git_history_max_depth,
                branch=(snapshot.branch if snapshot is not None else None),
                timeout_s=settings.ingestion_clone_timeout_s,
            )
        except Exception:
            _cleanup()
            raise
        return GitRepoHandle(repo=repo, cleanup=_cleanup, source="clone")

    return None
