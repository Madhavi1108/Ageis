"""Phase 19 integration: the /repositories/{id}/git/* endpoints over HTTP."""

from __future__ import annotations

import git
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.main import app
from app.models.base import Base

_ACTORS = [git.Actor("Ada", "ada@example.com"), git.Actor("Ben", "ben@example.com")]


def _build_repo(root):
    root.mkdir(parents=True, exist_ok=True)
    repo = git.Repo.init(root)

    def commit(msg, actor, files):
        for name, text in files.items():
            (root / name).write_text(text, encoding="utf-8")
        repo.index.add(list(files))
        repo.index.commit(msg, author=actor, committer=actor)

    commit("add invoice", _ACTORS[0], {
        "invoice.py": "def total(p, d):\n    return p * (1 - d)\n",
        "test_invoice.py": "def test_total():\n    assert True\n",
    })
    commit("tweak rounding", _ACTORS[1], {
        "invoice.py": "def total(p, d):\n    return round(p * (1 - d), 2)\n",
    })
    commit("fix: clamp discount", _ACTORS[0], {
        "invoice.py": "def total(p, d):\n    d = min(d, 0.5)\n    return round(p * (1 - d), 2)\n",
        "test_invoice.py": "def test_total():\n    assert True\n\ndef test_x():\n    assert True\n",
    })
    return root


@pytest.fixture
def client(tmp_path, acceptance_fixture_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'git_test.db'}")
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
            ingestion_local_roots=[str(tmp_path), str(acceptance_fixture_path.parent)],
            artifacts_root=str(tmp_path / "artifacts"),
            _env_file=None,
        )

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_settings] = _get_settings
    try:
        with TestClient(app) as c:
            yield c, tmp_path
    finally:
        app.dependency_overrides.clear()


def _ingest_local(c, path) -> str:
    repo_id = c.post(
        "/repositories", json={"source_type": "LOCAL", "url_or_path": str(path)}
    ).json()["id"]
    c.post(f"/repositories/{repo_id}/snapshots", json={})
    return repo_id


def test_history_and_churn_on_a_real_repo(client):
    c, tmp_path = client
    repo_id = _ingest_local(c, _build_repo(tmp_path / "src"))

    h = c.get(f"/repositories/{repo_id}/git/history")
    assert h.status_code == 200, h.text
    body = h.json()
    assert body["available"] is True
    assert body["commit_count"] == 3
    assert body["commits"][0]["message"].startswith("fix: clamp discount")
    assert body["commits"][0]["is_related_fix"] is True
    assert len(body["related_fixes"]) == 1
    # author emails are hashed, never raw
    assert all("@" not in cm["author_email_hash"] for cm in body["commits"])

    churn = c.get(f"/repositories/{repo_id}/git/churn").json()["churn"]
    by_path = {e["path"]: e for e in churn}
    assert by_path["invoice.py"]["commit_count"] == 3
    assert by_path["invoice.py"]["distinct_authors"] == 2

    # cached: a second call is identical
    assert c.get(f"/repositories/{repo_id}/git/history").json() == body


def test_blame_endpoint(client):
    c, tmp_path = client
    repo_id = _ingest_local(c, _build_repo(tmp_path / "src"))

    r = c.get(f"/repositories/{repo_id}/git/blame", params={"path": "invoice.py"})
    assert r.status_code == 200, r.text
    hunks = r.json()
    assert sum(h["line_count"] for h in hunks) == 3
    assert all(len(h["author_email_hash"]) == 64 for h in hunks)

    missing = c.get(f"/repositories/{repo_id}/git/blame")
    assert missing.status_code == 400
    assert missing.json()["code"] == "GIT_BLAME_PATH_REQUIRED"


def test_no_git_history_is_available_false_not_an_error(client, acceptance_fixture_path):
    c, _ = client
    repo_id = _ingest_local(c, acceptance_fixture_path)  # a plain dir, no .git
    body = c.get(f"/repositories/{repo_id}/git/context").json()
    assert body["available"] is False
    assert body["reason"]
    assert body["commits"] == []


def test_unknown_repository_is_404(client):
    c, _ = client
    r = c.get("/repositories/nope/git/history")
    assert r.status_code == 404
    assert r.json()["code"] == "GIT_REPOSITORY_NOT_FOUND"
