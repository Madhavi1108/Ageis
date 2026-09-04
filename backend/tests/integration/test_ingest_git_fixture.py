"""Ingest a real local git repository (not a plain directory).

Exercises the git-aware `open_local` branch of ingest_repository -- a real,
non-`local:`-prefixed commit_sha. This does NOT exercise the remote clone_shallow
network path (see docs/AEGIS_IMPLEMENTATION_PLAN.md Section 11 risk note: avoid
live GitHub calls in CI); that path is covered only by url_validator/git_client
unit tests.
"""

from __future__ import annotations

import git
import pytest

from app.ingestion.ingest import ingest_repository
from app.repository.repositories import RepositoryRepository
from app.schemas.repository import IngestRequest


@pytest.fixture
def git_repo_fixture(tmp_path):
    repo_dir = tmp_path / "src"
    repo_dir.mkdir()
    (repo_dir / "main.py").write_text("print('hello')\n")
    (repo_dir / "README.md").write_text("# hello\n")

    repo = git.Repo.init(repo_dir)
    repo.index.add(["main.py", "README.md"])
    repo.index.commit("initial commit", author=git.Actor("test", "test@example.com"))
    return repo_dir


def test_ingest_local_git_repo_uses_real_commit_sha(
    db_session, ingestion_settings, git_repo_fixture
):
    repo = RepositoryRepository(db_session).get_or_create(
        source_type="LOCAL", url_or_path=str(git_repo_fixture), name="git-fixture"
    )

    result = ingest_repository(
        db_session,
        repository=repo,
        request=IngestRequest(),
        settings=ingestion_settings,
    )

    assert result.status == "READY"
    assert not result.commit_sha.startswith("local:")
    assert len(result.commit_sha) == 40
    assert result.branch is not None
    assert result.file_count == 2
