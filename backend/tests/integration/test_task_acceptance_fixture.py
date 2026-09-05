"""Acceptance: submitting the Specification's example task text stores a Task
with a sensible type and the description intact.
See docs/AEGIS_IMPLEMENTATION_PLAN.md Section 14 "Phase-wise testing" Acceptance.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.main import app
from app.models.base import Base


@pytest.fixture
def client(tmp_path, acceptance_fixture_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'task_acceptance_test.db'}")
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

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_settings] = _get_settings
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def test_specification_example_task_is_stored_intact(client, acceptance_fixture_path):
    repo_id = client.post(
        "/repositories",
        json={"source_type": "LOCAL", "url_or_path": str(acceptance_fixture_path)},
    ).json()["id"]

    task_md = (acceptance_fixture_path / "task.md").read_text(encoding="utf-8")

    resp = client.post("/tasks", json={"repository_id": repo_id, "text": task_md})
    assert resp.status_code == 201, resp.text
    task = resp.json()["task"]

    # "a bug that must fully pass" (Specification Section 39) -> BUG.
    assert task["task_type"] == "BUG"
    # description intact: the concrete details the pipeline needs downstream.
    assert "calculate_total()" in task["description"]
    assert "0.5" in task["description"]
    assert "discount exceeds the configured maximum" in task["description"]
    assert resp.json()["normalization"]["truncated"] is False

    # Retrievable, as submitted.
    got = client.get(f"/tasks/{task['id']}").json()
    assert got["description"] == task["description"]
    assert got["state"] == "PENDING"
