"""Acceptance (docs/AEGIS_IMPLEMENTATION_PLAN.md Section 24): the acceptance
patch is reviewed, findings are evidence-backed with a severity, there is no
false CRITICAL, and two runs are deterministic.
"""

from __future__ import annotations

from app.analysis.analyze import analyze_snapshot
from app.ingestion.ingest import ingest_repository
from app.repository.repositories import RepositoryRepository
from app.repository.snapshots import SnapshotRepository
from app.schemas.repository import IngestRequest
from app.schemas.plan import EngineeringPlanAI
from app.schemas.implementation import EditOpsAI
from app.schemas.task import TaskCreate
from app.services import impact as impact_service
from app.services import implementation as implementation_service
from app.services import mapping as mapping_service
from app.services import planning as planning_service
from app.services import review as review_service
from app.services import tasks as tasks_service

_PLAN = EngineeringPlanAI.model_validate(
    {
        "problem_interpretation": "cap discount at 0.5",
        "assumptions": [],
        "files_to_inspect": ["invoice.py"],
        "files_to_modify": ["invoice.py"],
        "symbols_to_modify": ["invoice.py::calculate_total"],
        "dependencies": [],
        "steps": [
            {
                "id": "s1",
                "description": "clamp",
                "test_intent": "90==50",
                "evidence_refs": [],
            }
        ],
        "test_strategy": {"approach": "boundary"},
        "expected_behavior": "capped",
        "regression_risks": [],
        "rollback_strategy": "revert",
        "source": "AI",
        "confidence": {"value": 0.8, "basis": "INFERENCE"},
        "evidence": [],
    }
)
_EDIT = EditOpsAI.model_validate(
    {
        "edit_ops": [
            {
                "path": "invoice.py",
                "op": "replace",
                "anchor": "return price * (1 - discount)",
                "new": "discount = min(discount, 0.5)\n    return price * (1 - discount)",
                "plan_step_id": "s1",
                "rationale": "cap",
                "evidence": [],
            }
        ]
    }
)


class _Provider:
    name = "fake"

    def complete(self, *, template, schema, **_kw):
        if template == "planning":
            return _PLAN
        if template == "implementation":
            return _EDIT
        if template == "code_review":
            return schema.model_validate({"findings": []})
        raise AssertionError(template)


def _prepare(db_session, ingestion_settings, acceptance_fixture_path) -> str:
    repo = RepositoryRepository(db_session).get_or_create(
        source_type="LOCAL", url_or_path=str(acceptance_fixture_path), name="acc"
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
    task_id = tasks_service.create_task(
        db_session,
        settings=ingestion_settings,
        payload=TaskCreate(repository_id=repo.id, text=task_md),
    ).task.id
    mapping_service.run_mapping(
        db_session, settings=ingestion_settings, task_id=task_id
    )
    impact_service.get_or_compute_impact(
        db_session, settings=ingestion_settings, task_id=task_id
    )
    p = _Provider()
    planning_service.generate_plan(
        db_session, settings=ingestion_settings, task_id=task_id, provider=p
    )
    planning_service.validate_plan_for_task(db_session, task_id)
    implementation_service.generate_implementation(
        db_session, settings=ingestion_settings, task_id=task_id, provider=p
    )
    return task_id


def test_acceptance_patch_review_is_deterministic_and_no_false_critical(
    db_session, ingestion_settings, acceptance_fixture_path
):
    task_id = _prepare(db_session, ingestion_settings, acceptance_fixture_path)
    p = _Provider()

    a = review_service.get_or_review(
        db_session, settings=ingestion_settings, task_id=task_id, provider=p
    )
    b = review_service.get_or_review(
        db_session,
        settings=ingestion_settings,
        task_id=task_id,
        provider=p,
        refresh=True,
    )
    assert [f.model_dump() for f in a.findings] == [f.model_dump() for f in b.findings]

    assert not any(f.severity == "CRITICAL" for f in a.findings)
    for f in a.findings:
        assert f.file is not None
        assert f.evidence
        assert f.recommendation
    assert "ruff" in a.static_tools_run
