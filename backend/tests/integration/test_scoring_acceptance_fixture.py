"""Acceptance (docs/AEGIS_IMPLEMENTATION_PLAN.md Section 25): the three scores
for the acceptance patch are reproducible across runs, the contribution
breakdown explains each value, every signal carries a basis (+ an
unavailable_reason when it fell back to a prior), the clean patch fires no
hard gate, and PCS / CRS / RHP all land in 0..100.
"""

from __future__ import annotations

from app.analysis.analyze import analyze_snapshot
from app.ingestion.ingest import ingest_repository
from app.repository.repositories import RepositoryRepository
from app.repository.snapshots import SnapshotRepository
from app.schemas.implementation import EditOpsAI
from app.schemas.plan import EngineeringPlanAI
from app.schemas.repository import IngestRequest
from app.schemas.task import TaskCreate
from app.scoring.model_registry import SCORING_MODEL_VERSION
from app.services import impact as impact_service
from app.services import implementation as implementation_service
from app.services import mapping as mapping_service
from app.services import planning as planning_service
from app.services import review as review_service
from app.services import scoring as scoring_service
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
            {"id": "s1", "description": "clamp", "test_intent": "90==50", "evidence_refs": []}
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


def _prepare(db_session, ingestion_settings, acceptance_fixture_path) -> tuple[str, str]:
    repo = RepositoryRepository(db_session).get_or_create(
        source_type="LOCAL", url_or_path=str(acceptance_fixture_path), name="acc"
    )
    res = ingest_repository(
        db_session, repository=repo, request=IngestRequest(), settings=ingestion_settings
    )
    snap = SnapshotRepository(db_session).get(res.snapshot_id)
    analyze_snapshot(db_session, snapshot=snap, settings=ingestion_settings)
    task_md = (acceptance_fixture_path / "task.md").read_text(encoding="utf-8")
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
    planning_service.generate_plan(
        db_session, settings=ingestion_settings, task_id=task_id, provider=p
    )
    planning_service.validate_plan_for_task(db_session, task_id)
    implementation_service.generate_implementation(
        db_session, settings=ingestion_settings, task_id=task_id, provider=p
    )
    review_service.get_or_review(
        db_session, settings=ingestion_settings, task_id=task_id, provider=p
    )
    return task_id, repo.id


def test_scores_are_reproducible_and_explained(
    db_session, ingestion_settings, acceptance_fixture_path
):
    task_id, repo_id = _prepare(db_session, ingestion_settings, acceptance_fixture_path)

    conf_a, risk_a = scoring_service.get_or_score(
        db_session, settings=ingestion_settings, task_id=task_id
    )
    conf_b, risk_b = scoring_service.get_or_score(
        db_session, settings=ingestion_settings, task_id=task_id, refresh=True
    )

    def _no_ts(m):
        d = m.model_dump()
        d.pop("created_at", None)
        d["task_risk_profile"] = {
            k: v for k, v in d.get("task_risk_profile", {}).items() if k != "created_at"
        } if "task_risk_profile" in d else d.get("task_risk_profile")
        return d

    assert _no_ts(conf_a) == _no_ts(conf_b)
    assert _no_ts(risk_a) == _no_ts(risk_b)

    assert 0 <= conf_a.value <= 100
    assert conf_a.classification != "BLOCKED"
    assert conf_a.hard_gate == []
    assert conf_a.model_version == SCORING_MODEL_VERSION
    assert conf_a.value == round(conf_a.pcs_raw * conf_a.security_gate)
    assert 0 <= risk_a.value <= 100
    assert 0 <= risk_a.task_risk_profile.value <= 100
    assert risk_a.task_risk_profile.scope == "task"

    # every contribution is explained
    for s in conf_a.per_signal_contributions + risk_a.per_signal_contributions:
        assert s.basis in ("FACT", "INFERENCE")
        assert 0.0 <= s.normalized <= 1.0
        if s.unavailable_reason is None:
            assert s.basis == "FACT" or s.raw is not None
    # at least the coverage + churn signals are unavailable here
    reasons = {
        s.name
        for s in conf_a.per_signal_contributions
        if s.unavailable_reason is not None
    }
    assert "coverage" in reasons and "history_stable" in reasons

    health = scoring_service.get_or_health(
        db_session, settings=ingestion_settings, repository_id=repo_id
    )
    assert 0 <= health.value <= 100
    assert health.scope == "repository"
    assert health.model_version == SCORING_MODEL_VERSION
