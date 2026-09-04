import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.repository.artifacts import ArtifactRepository
from app.repository.files import FileRepository
from app.repository.repositories import RepositoryRepository
from app.repository.snapshots import SnapshotRepository
from app.ingestion.manifest import ManifestFile


@pytest.fixture
def session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    db = SessionLocal()
    yield db
    db.close()


def test_repository_get_or_create_is_idempotent(session):
    repo_repo = RepositoryRepository(session)
    first = repo_repo.get_or_create(source_type="LOCAL", url_or_path="/tmp/x", name="x")
    second = repo_repo.get_or_create(
        source_type="LOCAL", url_or_path="/tmp/x", name="x"
    )
    assert first.id == second.id


def test_repository_get_by_source_missing_returns_none(session):
    assert RepositoryRepository(session).get_by_source("LOCAL", "/nope") is None


def test_snapshot_create_get_and_dedup_by_commit(session):
    repo = RepositoryRepository(session).get_or_create(
        source_type="LOCAL", url_or_path="/tmp/x", name="x"
    )
    snap_repo = SnapshotRepository(session)
    created = snap_repo.create(
        repository_id=repo.id, commit_sha="abc123", branch="main", history_depth=1
    )

    assert snap_repo.get(created.id).id == created.id
    assert snap_repo.get_by_commit(repo.id, "abc123").id == created.id
    assert snap_repo.get_by_commit(repo.id, "does-not-exist") is None


def test_file_repository_bulk_create_and_replace(session):
    repo = RepositoryRepository(session).get_or_create(
        source_type="LOCAL", url_or_path="/tmp/x", name="x"
    )
    snapshot = SnapshotRepository(session).create(
        repository_id=repo.id, commit_sha="abc", branch=None, history_depth=0
    )
    files_repo = FileRepository(session)
    manifest = [
        ManifestFile(
            path="a.py",
            size_bytes=10,
            sha256="a" * 64,
            language="python",
            is_test=False,
            is_vendored=False,
        )
    ]
    files_repo.bulk_create(snapshot.id, manifest)
    assert len(files_repo.list_for_snapshot(snapshot.id)) == 1

    replacement = [
        ManifestFile(
            path="b.py",
            size_bytes=20,
            sha256="b" * 64,
            language="python",
            is_test=False,
            is_vendored=False,
        )
    ]
    files_repo.replace_for_snapshot(snapshot.id, replacement)
    rows = files_repo.list_for_snapshot(snapshot.id)
    assert [r.path for r in rows] == ["b.py"]


def test_artifact_repository_create_and_get(session):
    repo = RepositoryRepository(session).get_or_create(
        source_type="LOCAL", url_or_path="/tmp/x", name="x"
    )
    snapshot = SnapshotRepository(session).create(
        repository_id=repo.id, commit_sha="abc", branch=None, history_depth=0
    )
    artifact = ArtifactRepository(session).create(
        kind="WORKSPACE",
        store="FS",
        uri="/tmp/ws",
        retention="EPHEMERAL",
        snapshot_id=snapshot.id,
    )
    assert ArtifactRepository(session).get(artifact.id).uri == "/tmp/ws"
