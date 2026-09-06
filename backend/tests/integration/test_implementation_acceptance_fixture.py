"""Acceptance (docs/AEGIS_IMPLEMENTATION_PLAN.md Section 18): a real diff is
generated for the acceptance repo's invoice.py fix, the patch applies, the
original snapshot workspace is preserved, and each hunk traces to a plan step.
"""

from __future__ import annotations

from app.ai.provider import MockProvider
from app.analysis.analyze import analyze_snapshot
from app.ingestion.ingest import ingest_repository
from app.ingestion.workspace import workspace_dir
from app.repository.repositories import RepositoryRepository
from app.repository.snapshots import SnapshotRepository
from app.schemas.repository import IngestRequest
from app.schemas.task import TaskCreate
from app.services import impact as impact_service
from app.services import implementation as implementation_service
from app.services import mapping as mapping_service
from app.services import planning as planning_service
from app.services import tasks as tasks_service

_PLAN = {
    "problem_interpretation": "cap the discount rate at 0.5 in calculate_total",
    "assumptions": ["the discount argument is a fraction in [0, 1]"],
    "files_to_inspect": ["invoice.py"],
    "files_to_modify": ["invoice.py"],
    "symbols_to_modify": ["invoice.py::calculate_total"],
    "dependencies": [],
    "steps": [
        {
            "id": "s1",
            "description": "clamp discount to 0.5 before applying it",
            "test_intent": "a 90% discount behaves like a 50% discount",
            "evidence_refs": ["invoice.py::calculate_total"],
        }
    ],
    "test_strategy": {"approach": "add a boundary test at discount=0.9"},
    "expected_behavior": "calculate_total(100, 0.9) == 50.0",
    "regression_risks": ["existing no-discount path must still return price"],
    "rollback_strategy": "revert invoice.py to the snapshot version",
    "source": "AI",
    "confidence": {"value": 0.82, "basis": "INFERENCE"},
    "evidence": [
        {"kind": "symbol", "ref": "invoice.py::calculate_total", "detail": "target"}
    ],
}

_EDIT_OPS = {
    "edit_ops": [
        {
            "path": "invoice.py",
            "op": "replace",
            "anchor": "return price * (1 - discount)",
            "new": "discount = min(discount, 0.5)\n    return price * (1 - discount)",
            "plan_step_id": "s1",
            "rationale": "cap discount at 0.5 before applying it",
            "evidence": [
                {
                    "kind": "symbol",
                    "ref": "invoice.py::calculate_total",
                    "detail": "target",
                }
            ],
        }
    ]
}


def _prepare_approved_task(db_session, ingestion_settings, acceptance_fixture_path):
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
    snapshot = SnapshotRepository(db_session).get(result.snapshot_id)
    analyze_snapshot(db_session, snapshot=snapshot, settings=ingestion_settings)

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
    impact_service.get_or_compute_impact(
        db_session, settings=ingestion_settings, task_id=task_id
    )

    provider = MockProvider()
    provider.register("planning", task_id, _PLAN)
    planning_service.generate_plan(
        db_session, settings=ingestion_settings, task_id=task_id, provider=provider
    )
    validated = planning_service.validate_plan_for_task(db_session, task_id)
    assert validated.validation.verdict == "APPROVED"

    return task_id, snapshot.id, provider


def test_real_diff_generated_and_patch_applies(
    db_session, ingestion_settings, acceptance_fixture_path
):
    task_id, snapshot_id, provider = _prepare_approved_task(
        db_session, ingestion_settings, acceptance_fixture_path
    )
    provider.register("implementation", task_id, _EDIT_OPS)

    result = implementation_service.generate_implementation(
        db_session, settings=ingestion_settings, task_id=task_id, provider=provider
    )

    assert result.patch.touched_paths == ["invoice.py"]
    assert "min(discount, 0.5)" in result.patch.diff_text
    assert result.scope_violations == []
    assert result.traceability == {"s1": ["invoice.py"]}
    for op in result.edit_ops:
        assert op.plan_step_id == "s1"


def test_original_snapshot_workspace_is_preserved(
    db_session, ingestion_settings, acceptance_fixture_path
):
    task_id, snapshot_id, provider = _prepare_approved_task(
        db_session, ingestion_settings, acceptance_fixture_path
    )
    provider.register("implementation", task_id, _EDIT_OPS)

    ws_path = workspace_dir(snapshot_id, ingestion_settings)
    before = (ws_path / "invoice.py").read_text(encoding="utf-8")

    implementation_service.generate_implementation(
        db_session, settings=ingestion_settings, task_id=task_id, provider=provider
    )

    after = (ws_path / "invoice.py").read_text(encoding="utf-8")
    assert before == after
    assert "min(discount" not in after


def test_no_provider_configured_fails_loudly(
    db_session, ingestion_settings, acceptance_fixture_path
):
    from app.implementation.errors import ImplementationFailedError

    task_id, snapshot_id, provider = _prepare_approved_task(
        db_session, ingestion_settings, acceptance_fixture_path
    )
    try:
        implementation_service.generate_implementation(
            db_session, settings=ingestion_settings, task_id=task_id, provider=None
        )
        assert False, "expected ImplementationFailedError"
    except ImplementationFailedError:
        pass
