"""Acceptance (docs/AEGIS_IMPLEMENTATION_PLAN.md Section 26): verification on
the acceptance patch is reproducible, produces all seven criteria and a
four-field trace, never falsely reports VERIFIED when the suite could not run,
and turns NOT_VERIFIED on a scope/alignment violation. The false-complete rate
on the negative fixture is 0.
"""

from __future__ import annotations

from app.analysis.analyze import analyze_snapshot
from app.ingestion.ingest import ingest_repository
from app.repository.repositories import RepositoryRepository
from app.repository.snapshots import SnapshotRepository
from app.repository.verifications import VerificationRepository
from app.schemas.implementation import EditOpsAI
from app.schemas.plan import EngineeringPlanAI
from app.schemas.repository import IngestRequest
from app.schemas.task import TaskCreate
from app.services import impact as impact_service
from app.services import implementation as implementation_service
from app.services import mapping as mapping_service
from app.services import planning as planning_service
from app.services import tasks as tasks_service
from app.services import verification as verification_service

_PLAN = EngineeringPlanAI.model_validate(
    {
        "problem_interpretation": "cap discount at 0.5",
        "assumptions": [],
        "files_to_inspect": ["invoice.py"],
        "files_to_modify": ["invoice.py"],
        "symbols_to_modify": ["invoice.py::calculate_total"],
        "dependencies": [],
        "steps": [
            {"id": "s1", "description": "clamp", "test_intent": "90==50", "evidence_refs": []}
        ],
        "test_strategy": {"approach": "boundary"},
        "expected_behavior": "the discount is capped at 0.5",
        "regression_risks": [],
        "rollback_strategy": "revert invoice.py",
        "source": "AI",
        "confidence": {"value": 0.8, "basis": "INFERENCE"},
        "evidence": [],
    }
)
_CLEAN_EDIT = EditOpsAI.model_validate(
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
_UNPLANNED_EDIT = EditOpsAI.model_validate(
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
            },
            {
                "path": "STRAY_FILE.txt",
                "op": "create",
                "new": "unrelated\n",
                "plan_step_id": "s1",
                "rationale": "stray",
                "evidence": [],
            },
        ]
    }
)


class _Provider:
    name = "fake"

    def complete(self, *, template, schema, **_kw):
        if template == "planning":
            return _PLAN
        if template == "implementation":
            return self._edit
        if template == "code_review":
            return schema.model_validate({"findings": []})
        raise AssertionError(template)


def _prepare(db_session, ingestion_settings, fixture, edit) -> str:
    repo = RepositoryRepository(db_session).get_or_create(
        source_type="LOCAL", url_or_path=str(fixture), name="acc"
    )
    res = ingest_repository(
        db_session, repository=repo, request=IngestRequest(), settings=ingestion_settings
    )
    snap = SnapshotRepository(db_session).get(res.snapshot_id)
    analyze_snapshot(db_session, snapshot=snap, settings=ingestion_settings)
    task_md = (fixture / "task.md").read_text(encoding="utf-8")
    task_id = tasks_service.create_task(
        db_session,
        settings=ingestion_settings,
        payload=TaskCreate(repository_id=repo.id, text=task_md),
    ).task.id
    mapping_service.run_mapping(db_session, settings=ingestion_settings, task_id=task_id)
    impact_service.get_or_compute_impact(
        db_session, settings=ingestion_settings, task_id=task_id
    )
    p = _Provider()
    p._edit = edit
    planning_service.generate_plan(
        db_session, settings=ingestion_settings, task_id=task_id, provider=p
    )
    planning_service.validate_plan_for_task(db_session, task_id)
    implementation_service.generate_implementation(
        db_session, settings=ingestion_settings, task_id=task_id, provider=p
    )
    return task_id


def test_clean_patch_reproducible_all_criteria_and_trace(
    db_session, ingestion_settings, acceptance_fixture_path
):
    task_id = _prepare(
        db_session, ingestion_settings, acceptance_fixture_path, _CLEAN_EDIT
    )

    a = verification_service.get_or_verify(
        db_session, settings=ingestion_settings, task_id=task_id
    )
    b = verification_service.get_or_verify(
        db_session, settings=ingestion_settings, task_id=task_id, refresh=True
    )

    def _norm(m):
        d = m.model_dump()
        d.pop("created_at", None)
        d.pop("trace_artifact_id", None)
        return d

    assert _norm(a) == _norm(b)

    assert [c.name for c in a.criteria] == [
        "acceptance_tests_pass",
        "suite_green",
        "patch_reapplies",
        "scope_clean",
        "review_clean",
        "plan_alignment",
        "score_gate",
    ]
    # every criterion carries a verdict from the allowed set and a detail line
    for c in a.criteria:
        assert c.verdict in ("PASS", "FAIL", "UNKNOWN")
        assert c.detail
    # no criterion is a false FAIL on a clean patch
    assert not any(c.verdict == "FAIL" for c in a.criteria)
    # sandbox-free criteria are decided
    by = {c.name: c.verdict for c in a.criteria}
    assert by["patch_reapplies"] == "PASS"
    assert by["scope_clean"] == "PASS"
    assert by["plan_alignment"] == "PASS"

    # the suite never ran here -> must not claim VERIFIED (false-complete rate 0)
    assert a.verdict in ("PARTIAL", "NOT_VERIFIED")
    assert a.verdict == "PARTIAL"
    assert a.resulting_state == "AWAITING_APPROVAL"

    assert a.trace.why_file
    assert a.trace.why_change == "cap discount at 0.5"
    assert a.trace.why_safe
    assert a.replay_fidelity == 1.0

    # history chain: refresh appended a second row, one live
    rows = VerificationRepository(db_session).list_for_task(task_id)
    assert len(rows) == 2
    live = [r for r in rows if r.superseded_by is None]
    assert len(live) == 1


def test_unplanned_file_is_not_verified(
    db_session, ingestion_settings, acceptance_fixture_path
):
    task_id = _prepare(
        db_session, ingestion_settings, acceptance_fixture_path, _UNPLANNED_EDIT
    )
    res = verification_service.get_or_verify(
        db_session, settings=ingestion_settings, task_id=task_id
    )

    by = {c.name: c.verdict for c in res.criteria}
    assert by["scope_clean"] == "FAIL"
    assert by["plan_alignment"] == "FAIL"
    assert res.verdict == "NOT_VERIFIED"
    assert res.resulting_state == "FAILED"
    assert "STRAY_FILE.txt" in res.plan_alignment.unplanned_files
    assert "NOT safe to ship" in res.trace.why_safe
