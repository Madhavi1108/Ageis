"""Ingest the real test-repositories/aegis-acceptance fixture end to end.

See docs/AEGIS_IMPLEMENTATION_PLAN.md Section 11 Acceptance test: expected file count with
Python as the dominant language.
"""

from __future__ import annotations

import sys

from app.ingestion.ingest import ingest_repository
from app.repository.repositories import RepositoryRepository
from app.schemas.repository import IngestRequest


def test_ingest_acceptance_fixture(
    db_session, ingestion_settings, acceptance_fixture_path
):
    repo = RepositoryRepository(db_session).get_or_create(
        source_type="LOCAL",
        url_or_path=str(acceptance_fixture_path),
        name="aegis-acceptance",
    )

    result = ingest_repository(
        db_session,
        repository=repo,
        request=IngestRequest(),
        settings=ingestion_settings,
    )

    assert result.status == "READY"
    # invoice.py, utils.py, checkout.py, order_service.py, test_invoice.py, task.md
    # (checkout.py/order_service.py added in Phase 5 for real CALLS-edge coverage).
    assert result.file_count == 6
    assert result.languages["python"] == 5
    assert result.languages["markdown"] == 1
    assert result.commit_sha.startswith("local:")

    from app.ingestion.workspace import workspace_dir

    ws_path = workspace_dir(result.snapshot_id, ingestion_settings)
    assert ws_path.exists()
    assert (ws_path / "invoice.py").exists()

    if sys.platform != "win32":
        import os

        assert not os.access(ws_path / "invoice.py", os.W_OK)


def test_ingest_creates_workspace_artifact(
    db_session, ingestion_settings, acceptance_fixture_path
):
    repo = RepositoryRepository(db_session).get_or_create(
        source_type="LOCAL",
        url_or_path=str(acceptance_fixture_path),
        name="aegis-acceptance",
    )
    ingest_repository(
        db_session,
        repository=repo,
        request=IngestRequest(),
        settings=ingestion_settings,
    )

    from app.models.artifact import Artifact

    rows = db_session.query(Artifact).all()
    assert len(rows) == 1
    assert rows[0].kind == "WORKSPACE"
    assert rows[0].store == "FS"
