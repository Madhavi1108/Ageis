"""Acceptance (docs/AEGIS_IMPLEMENTATION_PLAN.md Section 19): for the
acceptance task, at least one boundary test for discount==max and
discount>max is created and references the target symbol; no policy gap is
reported once both kinds are present.
"""

from __future__ import annotations

from app.ai.provider import MockProvider
from app.analysis.analyze import analyze_snapshot
from app.ingestion.ingest import ingest_repository
from app.repository.repositories import RepositoryRepository
from app.repository.snapshots import SnapshotRepository
from app.schemas.repository import IngestRequest
from app.schemas.task import TaskCreate
from app.services import impact as impact_service
from app.services import implementation as implementation_service
from app.services import mapping as mapping_service
from app.services import planning as planning_service
from app.services import tasks as tasks_service
from app.services import testing as testing_service

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


def _prepare_implemented_task(db_session, ingestion_settings, acceptance_fixture_path):
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

    return task_id, provider


def test_boundary_and_negative_cases_created_for_the_target_symbol(
    db_session, ingestion_settings, acceptance_fixture_path
):
    task_id, provider = _prepare_implemented_task(
        db_session, ingestion_settings, acceptance_fixture_path
    )
    provider.register("test_synthesis", task_id, _TEST_CASES)

    result = testing_service.generate_tests(
        db_session, settings=ingestion_settings, task_id=task_id, provider=provider
    )

    kinds_by_symbol: dict[str, set[str]] = {}
    for case in result.test_cases:
        kinds_by_symbol.setdefault(case.target_symbol, set()).add(case.kind)
        assert case.status == "GENERATED"

    assert {"BOUNDARY", "NEGATIVE"} <= kinds_by_symbol["invoice.py::calculate_total"]
    assert result.policy_gaps == []
    assert set(result.targeted_set) == {
        "test_discount_at_max",
        "test_discount_above_max",
    }


def test_policy_gap_reported_when_a_kind_is_missing(
    db_session, ingestion_settings, acceptance_fixture_path
):
    task_id, provider = _prepare_implemented_task(
        db_session, ingestion_settings, acceptance_fixture_path
    )
    only_boundary = {"test_cases": [_TEST_CASES["test_cases"][0]]}
    provider.register("test_synthesis", task_id, only_boundary)

    result = testing_service.generate_tests(
        db_session, settings=ingestion_settings, task_id=task_id, provider=provider
    )

    assert result.policy_gaps == [
        "invoice.py::calculate_total: missing ['NEGATIVE'] case(s)"
    ]
