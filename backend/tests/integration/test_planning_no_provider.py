"""Phase 9: with ai_provider="none" the pipeline still produces a plan -- the
deterministic rule-based fallback (docs/AEGIS_IMPLEMENTATION_PLAN.md Section 17:
"the pipeline runs both without a real provider (fallback) and with one").
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
    engine = create_engine(f"sqlite:///{tmp_path / 'noprov_test.db'}")
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
            ai_provider="none",
            _env_file=None,
        )

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_settings] = _get_settings
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.clear()


def test_fallback_plan_is_produced_and_validates(client, acceptance_fixture_path):
    repo_id = client.post(
        "/repositories",
        json={"source_type": "LOCAL", "url_or_path": str(acceptance_fixture_path)},
    ).json()["id"]
    snapshot_id = client.post(f"/repositories/{repo_id}/snapshots", json={}).json()[
        "snapshot_id"
    ]
    client.post(f"/repositories/{repo_id}/snapshots/{snapshot_id}/analysis", json={})
    task_md = (acceptance_fixture_path / "task.md").read_text(encoding="utf-8")
    task_id = client.post(
        "/tasks", json={"repository_id": repo_id, "text": task_md}
    ).json()["task"]["id"]
    client.post("/analysis/map", json={"task_id": task_id})
    client.get(f"/tasks/{task_id}/impact")

    gen = client.post(f"/tasks/{task_id}/plan")
    assert gen.status_code == 201, gen.text
    plan = gen.json()
    assert plan["source"] == "RULE_BASED_FALLBACK"
    assert plan["confidence"]["value"] <= 0.3
    assert plan["files_to_modify"]  # names a real localisation candidate
    assert plan["steps"][0]["test_intent"]

    val = client.post(f"/tasks/{task_id}/plan/validate").json()
    assert val["validation"]["verdict"] in ("APPROVED", "REVISE")
