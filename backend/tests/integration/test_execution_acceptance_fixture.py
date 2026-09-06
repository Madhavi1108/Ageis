"""Acceptance (docs/AEGIS_IMPLEMENTATION_PLAN.md Section 20): the acceptance
repo's generated tests execute; without Docker the result is
PARTIALLY_SUPPORTED with a documented reason (proven here, since this dev
environment has no daemon); with Docker available (``@pytest.mark.docker``,
auto-skipped otherwise) the real container path runs to a real PASS.
"""

from __future__ import annotations

import pytest

from app.ai.provider import MockProvider
from app.analysis.analyze import analyze_snapshot
from app.ingestion.ingest import ingest_repository
from app.repository.repositories import RepositoryRepository
from app.repository.snapshots import SnapshotRepository
from app.sandbox import docker_backend
from app.schemas.repository import IngestRequest
from app.schemas.task import TaskCreate
from app.services import execution as execution_service
from app.services import impact as impact_service
from app.services import implementation as implementation_service
from app.services import mapping as mapping_service
from app.services import planning as planning_service
from app.services import tasks as tasks_service
from app.services import testing as testing_service

_PLAN = {
    "problem_interpretation": "cap the discount rate at 0.5 in calculate_total",
    "assumptions": [],
    "files_to_inspect": ["invoice.py"],
    "files_to_modify": ["invoice.py"],
    "symbols_to_modify": ["invoice.py::calculate_total"],
    "dependencies": [],
    "steps": [
        {
            "id": "s1",
            "description": "clamp discount to 0.5 before applying it",
            "test_intent": "a 90% discount behaves like a 50% discount",
            "evidence_refs": [],
        }
    ],
    "test_strategy": {"approach": "add a boundary test at discount=0.9"},
    "expected_behavior": "calculate_total(100, 0.9) == 50.0",
    "regression_risks": [],
    "rollback_strategy": "revert invoice.py to the snapshot version",
    "source": "AI",
    "confidence": {"value": 0.82, "basis": "INFERENCE"},
    "evidence": [],
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
            "evidence": [],
        }
    ]
}

_TEST_CASES = {
    "test_cases": [
        {
            "name": "test_discount_at_max",
            "path": "test_invoice_boundary.py",
            "target_symbol": "invoice.py::calculate_total",
            "kind": "BOUNDARY",
            "rationale": "discount exactly at the cap",
            "code": (
                "from invoice import calculate_total\n\n\n"
                "def test_discount_at_max():\n"
                "    assert calculate_total(100.0, 0.5) == 50.0\n"
            ),
            "evidence": [],
        },
        {
            "name": "test_discount_above_max",
            "path": "test_invoice_negative.py",
            "target_symbol": "invoice.py::calculate_total",
            "kind": "NEGATIVE",
            "rationale": "a discount above the cap must still be capped",
            "code": (
                "from invoice import calculate_total\n\n\n"
                "def test_discount_above_max():\n"
                "    assert calculate_total(100.0, 0.9) == 50.0\n"
            ),
            "evidence": [],
        },
    ]
}


def _prepare_tested_task(db_session, ingestion_settings, acceptance_fixture_path):
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

    provider.register("implementation", task_id, _EDIT_OPS)
    implementation_service.generate_implementation(
        db_session, settings=ingestion_settings, task_id=task_id, provider=provider
    )

    provider.register("test_synthesis", task_id, _TEST_CASES)
    testing_service.generate_tests(
        db_session, settings=ingestion_settings, task_id=task_id, provider=provider
    )

    return task_id


def test_no_docker_is_partially_supported_with_reason(
    db_session, ingestion_settings, acceptance_fixture_path
):
    task_id = _prepare_tested_task(
        db_session, ingestion_settings, acceptance_fixture_path
    )

    result = execution_service.execute_tests(
        db_session, settings=ingestion_settings, task_id=task_id
    )

    assert result.outcome == "PARTIALLY_SUPPORTED"
    assert result.reason and "docker" in result.reason.lower()
    assert result.results == []


@pytest.mark.docker
@pytest.mark.skipif(
    not docker_backend.is_available(), reason="requires a running Docker daemon"
)
def test_real_docker_runs_generated_tests_to_pass(
    db_session, ingestion_settings, acceptance_fixture_path
):
    task_id = _prepare_tested_task(
        db_session, ingestion_settings, acceptance_fixture_path
    )

    result = execution_service.execute_tests(
        db_session, settings=ingestion_settings, task_id=task_id
    )

    assert result.outcome == "PASS"
    assert result.results
    assert all(r.outcome == "PASS" for r in result.results)
