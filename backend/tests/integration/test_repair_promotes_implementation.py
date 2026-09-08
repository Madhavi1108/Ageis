"""Phase 24 wiring fix (docs/AEGIS_IMPLEMENTATION_PLAN.md Section 32): a
REPAIRED repair-loop result is promoted onto the task's Implementation row in
place, so ``execute_retry`` / verification reconstruct the *fixed* workspace.

Without this the loop goes green only in its throwaway workspace and the run can
never reach VERIFIED through the repair path.
"""

from __future__ import annotations

from app.ai.provider import MockProvider
from app.analysis.analyze import analyze_snapshot
from app.ingestion.ingest import ingest_repository
from app.repository.implementations import ImplementationRepository
from app.repository.repositories import RepositoryRepository
from app.repository.snapshots import SnapshotRepository
from app.schemas.implementation import EditOp
from app.schemas.repository import IngestRequest
from app.schemas.task import TaskCreate
from app.services import impact as impact_service
from app.services import implementation as implementation_service
from app.services import mapping as mapping_service
from app.services import planning as planning_service
from app.services import tasks as tasks_service

_PLAN = {
    "problem_interpretation": "clamp the discount to the configured maximum in calculate_total",
    "assumptions": ["discount is a fraction in [0, 1]"],
    "files_to_inspect": ["invoice.py"],
    "files_to_modify": ["invoice.py"],
    "symbols_to_modify": ["invoice.py::calculate_total"],
    "dependencies": [],
    "steps": [
        {
            "id": "s1",
            "description": "clamp discount before applying it",
            "test_intent": "a 90% discount behaves like a 50% discount",
            "evidence_refs": ["invoice.py::calculate_total"],
        }
    ],
    "test_strategy": {"approach": "boundary test at discount=0.9"},
    "expected_behavior": "calculate_total(100, 0.9) == 50.0",
    "regression_risks": ["no-discount path unchanged"],
    "rollback_strategy": "revert invoice.py",
    "source": "AI",
    "confidence": {"value": 0.8, "basis": "INFERENCE"},
    "evidence": [],
}

# deliberately the wrong constant
_INCOMPLETE_IMPL = {
    "edit_ops": [
        {
            "path": "invoice.py",
            "op": "replace",
            "anchor": "return price * (1 - discount)",
            "old": "return price * (1 - discount)",
            "new": "return price * (1 - min(discount, 0.6))",
            "plan_step_id": "s1",
            "rationale": "clamp",
            "evidence": [],
        }
    ]
}

_REPAIR_OP = EditOp.model_validate(
    {
        "path": "invoice.py",
        "op": "replace",
        "anchor": "return price * (1 - min(discount, 0.6))",
        "old": "return price * (1 - min(discount, 0.6))",
        "new": "return price * (1 - min(discount, 0.5))",
        "plan_step_id": "repair",
        "rationale": "use the configured maximum",
        "evidence": [],
    }
)


def test_apply_repaired_ops_stacks_onto_the_row_in_place(
    db_session, ingestion_settings, acceptance_fixture_path
):
    repo = RepositoryRepository(db_session).get_or_create(
        source_type="LOCAL", url_or_path=str(acceptance_fixture_path), name="aegis-acceptance"
    )
    ingested = ingest_repository(
        db_session, repository=repo, request=IngestRequest(), settings=ingestion_settings
    )
    analyze_snapshot(
        db_session,
        snapshot=SnapshotRepository(db_session).get(ingested.snapshot_id),
        settings=ingestion_settings,
    )
    task_id = tasks_service.create_task(
        db_session,
        settings=ingestion_settings,
        payload=TaskCreate(
            repository_id=repo.id,
            text=(acceptance_fixture_path / "task.md").read_text(encoding="utf-8"),
        ),
    ).task.id
    mapping_service.run_mapping(db_session, settings=ingestion_settings, task_id=task_id)
    impact_service.get_or_compute_impact(
        db_session, settings=ingestion_settings, task_id=task_id
    )

    provider = MockProvider()
    provider.register("planning", task_id, _PLAN)
    provider.register("implementation", task_id, _INCOMPLETE_IMPL)
    planning_service.generate_plan(
        db_session, settings=ingestion_settings, task_id=task_id, provider=provider
    )
    assert (
        planning_service.validate_plan_for_task(db_session, task_id).validation.verdict
        == "APPROVED"
    )
    implementation_service.generate_implementation(
        db_session, settings=ingestion_settings, task_id=task_id, provider=provider
    )

    before = ImplementationRepository(db_session).get_latest_by_task(task_id)
    assert len(before.edit_ops) == 1
    assert "min(discount, 0.6)" in before.edit_ops[0]["new"]

    promoted = implementation_service.apply_repaired_ops(
        db_session, settings=ingestion_settings, task_id=task_id, repair_ops=[_REPAIR_OP]
    )

    after = ImplementationRepository(db_session).get_latest_by_task(task_id)
    # same row (in place -- bindings from test cases / executions stay valid)
    assert after.id == before.id
    assert after.version == before.version
    # the incomplete op and the repair op are now both recorded, in order
    assert len(after.edit_ops) == 2
    assert after.edit_ops[-1]["new"] == "return price * (1 - min(discount, 0.5))"
    # the patch + diff reflect the repaired code, not the incomplete one
    assert promoted.patch.touched_paths == ["invoice.py"]
    assert "min(discount, 0.5)" in promoted.patch.diff_text
    assert "min(discount, 0.6)" not in promoted.patch.diff_text
