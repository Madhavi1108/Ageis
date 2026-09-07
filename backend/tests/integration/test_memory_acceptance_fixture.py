"""Acceptance (docs/AEGIS_IMPLEMENTATION_PLAN.md Section 28, ADR-0016): the
Spec scenario -- "Incorrect discount calculation" then "Discount limit
incorrectly applied" against the acceptance repo.

* Task A reaches VERIFIED -> an EngineeringMemory record with every section.
* Task B (similar issue) retrieves A as ranked, provenance-labelled,
  non-authoritative evidence: in its mapping candidates and its planning prompt.
* A's patch is never applied to B.
* With ``memory_enabled=False`` B's mapping is unchanged.
"""

from __future__ import annotations

import pytest

from app.analysis.analyze import analyze_snapshot
from app.core.config import Settings
from app.ingestion.ingest import ingest_repository
from app.memory import MEMORY_LABEL
from app.repository.engineering_memory import EngineeringMemoryRepository
from app.repository.repositories import RepositoryRepository
from app.repository.repository_knowledge import RepositoryKnowledgeRepository
from app.repository.snapshots import SnapshotRepository
from app.schemas.implementation import EditOpsAI
from app.schemas.plan import EngineeringPlanAI
from app.schemas.repository import IngestRequest
from app.schemas.task import TaskCreate
from app.services import impact as impact_service
from app.services import implementation as implementation_service
from app.services import mapping as mapping_service
from app.services import memory as memory_service
from app.services import planning as planning_service
from app.services import tasks as tasks_service
from app.services import verification as verification_service

_ISSUE_A = (
    "Incorrect discount calculation: applying a discount above 50% still "
    "charges the full requested discount instead of capping it. Fix "
    "calculate_total in the invoice module so any discount above 0.5 is capped."
)
_ISSUE_B = (
    "Discount limit incorrectly applied: calculate_total in the invoice module "
    "does not cap the discount at 0.5 for very large discounts."
)

_PLAN = EngineeringPlanAI.model_validate(
    {
        "problem_interpretation": "cap discount at 0.5 in calculate_total",
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

    def __init__(self) -> None:
        self.rendered_memory_hits: str | None = None

    def complete(self, *, template, variables=None, schema, **_kw):
        if template == "planning":
            if variables is not None:
                self.rendered_memory_hits = variables.get("memory_hits")
            return _PLAN
        if template == "implementation":
            return _EDIT
        if template == "code_review":
            return schema.model_validate({"findings": []})
        raise AssertionError(template)


@pytest.fixture
def settings_on(tmp_path, acceptance_fixture_path):
    return Settings(
        ingestion_local_roots=[str(acceptance_fixture_path.parent)],
        artifacts_root=str(tmp_path / "artifacts"),
        memory_enabled=True,
        _env_file=None,
    )


@pytest.fixture
def settings_off(tmp_path, acceptance_fixture_path):
    return Settings(
        ingestion_local_roots=[str(acceptance_fixture_path.parent)],
        artifacts_root=str(tmp_path / "artifacts"),
        memory_enabled=False,
        _env_file=None,
    )


def _repo_and_snapshot(db, settings, fixture):
    repo = RepositoryRepository(db).get_or_create(
        source_type="LOCAL", url_or_path=str(fixture), name="acc"
    )
    res = ingest_repository(
        db, repository=repo, request=IngestRequest(), settings=settings
    )
    snap = SnapshotRepository(db).get(res.snapshot_id)
    analyze_snapshot(db, snapshot=snap, settings=settings)
    return repo


def _drive_task(db, settings, repo, issue_text, provider) -> str:
    task_id = tasks_service.create_task(
        db, settings=settings, payload=TaskCreate(repository_id=repo.id, text=issue_text)
    ).task.id
    mapping_service.run_mapping(db, settings=settings, task_id=task_id)
    impact_service.get_or_compute_impact(db, settings=settings, task_id=task_id)
    planning_service.generate_plan(db, settings=settings, task_id=task_id, provider=provider)
    planning_service.validate_plan_for_task(db, task_id)
    implementation_service.generate_implementation(
        db, settings=settings, task_id=task_id, provider=provider
    )
    return task_id


def _verify_and_approve(db, settings, task_id, provider) -> None:
    verification_service.get_or_verify(
        db, settings=settings, task_id=task_id, provider=provider
    )
    verification_service.resolve_decision(
        db,
        settings=settings,
        task_id=task_id,
        decision="APPROVE",
        reason="sandbox validated manually",
        actor="approver@x",
    )


def test_scenario_prior_task_is_retrieved_as_non_authoritative_evidence(
    db_session, settings_on, acceptance_fixture_path
):
    repo = _repo_and_snapshot(db_session, settings_on, acceptance_fixture_path)
    p = _Provider()

    task_a = _drive_task(db_session, settings_on, repo, _ISSUE_A, p)
    _verify_and_approve(db_session, settings_on, task_a, p)

    # --- the memory record has every section ---------------------------- #
    mem = EngineeringMemoryRepository(db_session).get_by_task(task_a)
    assert mem is not None
    assert mem.outcome == "VERIFIED"
    assert mem.verification_verdict == "VERIFIED"
    assert "discount" in mem.issue_text_sanitized.lower()
    assert "invoice.py::calculate_total" in mem.touched_symbols
    assert "invoice.py" in mem.touched_files
    assert mem.fix_summary
    assert mem.plan_ref["symbols_to_modify"] == ["invoice.py::calculate_total"]
    assert mem.patch_ref  # the DIFF artifact id
    assert mem.review_summary["reviewed"] is True

    knowledge = RepositoryKnowledgeRepository(db_session).get_by_repository(repo.id)
    assert knowledge is not None and knowledge.task_count == 1
    assert any(e["path"] == "invoice.py" for e in knowledge.risky_files)

    # --- task B retrieves A -------------------------------------------- #
    p_b = _Provider()
    task_b = _drive_task(db_session, settings_on, repo, _ISSUE_B, p_b)

    hits = memory_service.search(
        db_session,
        settings=settings_on,
        query=_ISSUE_B,
        repository_id=repo.id,
        exclude_task_id=task_b,
    )
    assert hits and hits[0].task_id == task_a
    assert hits[0].label == MEMORY_LABEL
    assert hits[0].provenance.startswith(f"task {task_a} (VERIFIED,")
    assert hits[0].similarity > 0

    # B's mapping carries a memory-sourced, non-authoritative candidate for invoice.py
    b_map = mapping_service.get_mapping(db_session, task_b)
    inv = next(c for c in b_map.candidates if c.path == "invoice.py")
    assert "INFERENCE" in inv.labels
    assert any(
        "historical" in e.detail.lower() and task_a in e.detail for e in inv.evidence
    )

    # B's planning prompt received A's provenance as memory_hits
    assert p_b.rendered_memory_hits is not None
    assert task_a in p_b.rendered_memory_hits
    assert "verify" in p_b.rendered_memory_hits.lower()

    # A's patch was NOT copied into B -- B generated its own implementation
    from app.repository.implementations import ImplementationRepository

    impl_a = ImplementationRepository(db_session).get_latest_by_task(task_a)
    impl_b = ImplementationRepository(db_session).get_latest_by_task(task_b)
    assert impl_b.id != impl_a.id
    assert impl_b.task_id == task_b


def test_disabled_flag_reproduces_pre_memory_mapping(
    db_session, settings_off, acceptance_fixture_path
):
    repo = _repo_and_snapshot(db_session, settings_off, acceptance_fixture_path)
    p = _Provider()
    task_a = _drive_task(db_session, settings_off, repo, _ISSUE_A, p)
    _verify_and_approve(db_session, settings_off, task_a, p)

    # no memory row was written
    assert EngineeringMemoryRepository(db_session).get_by_task(task_a) is None

    task_b = _drive_task(db_session, settings_off, repo, _ISSUE_B, _Provider())
    b_map = mapping_service.get_mapping(db_session, task_b)
    for c in b_map.candidates:
        for e in c.evidence:
            assert "historical" not in e.detail.lower()
