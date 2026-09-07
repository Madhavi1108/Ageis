"""Phase 19 integration: the /github/* passthrough + issue import over HTTP,
with the GitHub client wired to a mocked transport.
"""

from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.github.client import GitHubClient
from app.github.deps import get_github_client
from app.main import app
from app.models.base import Base


def _handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/repos/octo/demo":
        return httpx.Response(
            200,
            json={
                "full_name": "octo/demo",
                "default_branch": "main",
                "private": False,
                "html_url": "https://github.test/octo/demo",
                "description": "demo",
            },
        )
    if path == "/repos/octo/demo/issues/42":
        return httpx.Response(
            200,
            json={
                "number": 42,
                "title": "Discount not capped",
                "body": "totals can go negative",
                "state": "open",
                "html_url": "https://github.test/octo/demo/issues/42",
            },
        )
    return httpx.Response(404, json={"message": "nope"})


@pytest.fixture
def client(tmp_path, acceptance_fixture_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'github_test.db'}")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

    def _get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def _get_settings():
        return Settings(
            ingestion_local_roots=[str(acceptance_fixture_path.parent)],
            artifacts_root=str(tmp_path / "artifacts"),
            _env_file=None,
        )

    def _get_client():
        return GitHubClient(
            token=None,
            base_url="https://api.github.test",
            transport=httpx.MockTransport(_handler),
        )

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_settings] = _get_settings
    app.dependency_overrides[get_github_client] = _get_client
    try:
        with TestClient(app) as c:
            yield c, acceptance_fixture_path
    finally:
        app.dependency_overrides.clear()


def test_get_repo_and_issue(client):
    c, _ = client
    r = c.get("/github/repos/octo/demo")
    assert r.status_code == 200
    assert r.json()["full_name"] == "octo/demo"

    i = c.get("/github/repos/octo/demo/issues/42")
    assert i.status_code == 200
    assert i.json()["title"] == "Discount not capped"


def test_get_repo_404_maps_to_structured_error(client):
    c, _ = client
    r = c.get("/github/repos/octo/missing")
    assert r.status_code == 404
    assert r.json()["code"] == "GITHUB_NOT_FOUND"


def test_import_issue_is_idempotent(client):
    c, fixture = client
    repo_id = c.post(
        "/repositories", json={"source_type": "LOCAL", "url_or_path": str(fixture)}
    ).json()["id"]

    first = c.post(
        "/github/repos/octo/demo/issues/42/import",
        params={"repository_id": repo_id},
    )
    assert first.status_code == 201, first.text
    body = first.json()
    assert body["source"] == "GITHUB"
    assert body["external_ref"] == "42"

    second = c.post(
        "/github/repos/octo/demo/issues/42/import",
        params={"repository_id": repo_id},
    )
    assert second.status_code == 201
    assert second.json()["id"] == body["id"]  # deduped, same row


def test_import_issue_unknown_repository_is_404(client):
    c, _ = client
    r = c.post(
        "/github/repos/octo/demo/issues/42/import", params={"repository_id": "nope"}
    )
    assert r.status_code == 404
