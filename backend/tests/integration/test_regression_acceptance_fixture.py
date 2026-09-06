"""Acceptance (docs/AEGIS_IMPLEMENTATION_PLAN.md Section 23): the classification
+ selection for the acceptance task is deterministic; mode=full covers the whole
corpus; every RELATED/REGRESSION entry names why.
"""

from __future__ import annotations

from app.analysis.analyze import analyze_snapshot
from app.ingestion.ingest import ingest_repository
from app.repository.repositories import RepositoryRepository
from app.repository.snapshots import SnapshotRepository
from app.schemas.repository import IngestRequest
from app.schemas.task import TaskCreate
from app.services import mapping as mapping_service
from app.services import regression as regression_service
from app.services import tasks as tasks_service


def _prepare(db_session, ingestion_settings, acceptance_fixture_path) -> str:
    repo = RepositoryRepository(db_session).get_or_create(
        source_type="LOCAL",
        url_or_path=str(acceptance_fixture_path),
        name="aegis-acceptance",
    )
    res = ingest_repository(
        db_session,
        repository=repo,
        request=IngestRequest(),
        settings=ingestion_settings,
    )
    snap = SnapshotRepository(db_session).get(res.snapshot_id)
    analyze_snapshot(db_session, snapshot=snap, settings=ingestion_settings)

    task_md = (acceptance_fixture_path / "task.md").read_text(encoding="utf-8")
    created = tasks_service.create_task(
        db_session,
        settings=ingestion_settings,
        payload=TaskCreate(repository_id=repo.id, text=task_md),
    )
    task_id = created.task.id
    mapping_service.run_mapping(
        db_session, settings=ingestion_settings, task_id=task_id
    )
    # impact analysis is computed lazily by the regression service's dependency;
    # trigger it explicitly here via the impact service
    from app.services import impact as impact_service

    impact_service.get_or_compute_impact(
        db_session, settings=ingestion_settings, task_id=task_id
    )
    return task_id


def test_deterministic_and_full_covers_everything(
    db_session, ingestion_settings, acceptance_fixture_path
):
    task_id = _prepare(db_session, ingestion_settings, acceptance_fixture_path)

    a = regression_service.get_or_plan(
        db_session, settings=ingestion_settings, task_id=task_id, mode="smart"
    )
    b = regression_service.get_or_plan(
        db_session,
        settings=ingestion_settings,
        task_id=task_id,
        mode="smart",
        refresh=True,
    )
    assert [t.model_dump() for t in a.plan.tests] == [
        t.model_dump() for t in b.plan.tests
    ]
    assert a.plan.selection == b.plan.selection

    # every non-TARGETED/non-FULL entry explains itself
    for t in a.plan.tests:
        if t.classification in ("RELATED", "REGRESSION"):
            assert t.rationale
            assert (
                t.covers_symbol is not None
                or t.hops is not None
                or "prior" in t.rationale
            )

    full = regression_service.get_or_plan(
        db_session,
        settings=ingestion_settings,
        task_id=task_id,
        mode="full",
        refresh=True,
    )
    assert set(full.plan.selection["pre_verification"]) == {
        t.test_id for t in full.plan.tests
    }
    assert full.plan.full_suite_count == len(full.plan.tests)


def test_invoice_tests_are_targeted(
    db_session, ingestion_settings, acceptance_fixture_path
):
    task_id = _prepare(db_session, ingestion_settings, acceptance_fixture_path)
    res = regression_service.get_or_plan(
        db_session, settings=ingestion_settings, task_id=task_id
    )
    invoice = [t for t in res.plan.tests if t.test_id.startswith("test_invoice.py")]
    assert invoice
    assert all(t.classification == "TARGETED" for t in invoice)
