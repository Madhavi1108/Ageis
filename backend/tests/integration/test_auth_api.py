"""Phase 21 integration: the opt-in API-key auth gate over HTTP."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.main import app
from app.models.base import Base

_KEYS = {"vv": "viewer", "oo": "operator", "aa": "approver"}


def _mk_client(*, auth_enabled: bool):
    def _factory(tmp_path, acceptance_fixture_path):
        engine = create_engine(f"sqlite:///{tmp_path / 'auth_test.db'}")
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
                auth_enabled=auth_enabled,
                api_keys=_KEYS,
                _env_file=None,
            )

        app.dependency_overrides[get_db] = _get_db
        app.dependency_overrides[get_settings] = _get_settings
        return TestClient(app), acceptance_fixture_path

    return _factory


@pytest.fixture
def auth_client(tmp_path, acceptance_fixture_path):
    c, fx = _mk_client(auth_enabled=True)(tmp_path, acceptance_fixture_path)
    try:
        yield c, fx
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def open_client(tmp_path, acceptance_fixture_path):
    c, fx = _mk_client(auth_enabled=False)(tmp_path, acceptance_fixture_path)
    try:
        yield c, fx
    finally:
        app.dependency_overrides.clear()


def _repo_body(fx):
    return {"source_type": "LOCAL", "url_or_path": str(fx)}


def test_disabled_auth_needs_no_key(open_client):
    c, fx = open_client
    assert c.post("/repositories", json=_repo_body(fx)).status_code == 201


def test_get_routes_are_open_even_with_auth_on(auth_client):
    c, _ = auth_client
    assert c.get("/tasks").status_code == 200
    assert c.get("/jobs").status_code == 200


def test_mutating_route_requires_a_key(auth_client):
    c, fx = auth_client
    assert c.post("/repositories", json=_repo_body(fx)).status_code == 401
    r = c.post("/repositories", json=_repo_body(fx), headers={"x-api-key": "oo"})
    assert r.status_code == 201, r.text


def test_viewer_key_is_forbidden_on_mutation(auth_client):
    c, fx = auth_client
    r = c.post("/repositories", json=_repo_body(fx), headers={"x-api-key": "vv"})
    assert r.status_code == 403
    assert r.json()["code"] == "FORBIDDEN"


def test_approver_routes_need_approver(auth_client):
    c, fx = auth_client
    repo_id = c.post(
        "/repositories", json=_repo_body(fx), headers={"x-api-key": "oo"}
    ).json()["id"]
    task_md = (fx / "task.md").read_text(encoding="utf-8")
    task_id = c.post(
        "/tasks",
        json={"repository_id": repo_id, "text": task_md},
        headers={"x-api-key": "oo"},
    ).json()["task"]["id"]

    body = {"decision": "APPROVE", "reason": "x", "actor": "op"}
    # operator key -> 403 on an approver route (even though the task isn't awaiting)
    assert (
        c.post(
            f"/tasks/{task_id}/verification/decision",
            json=body,
            headers={"x-api-key": "oo"},
        ).status_code
        == 403
    )
    # approver key gets past the gate (then 409: not awaiting a decision)
    assert (
        c.post(
            f"/tasks/{task_id}/verification/decision",
            json=body,
            headers={"x-api-key": "aa"},
        ).status_code
        == 409
    )
