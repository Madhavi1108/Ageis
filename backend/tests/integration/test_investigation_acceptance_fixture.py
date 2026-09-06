"""Acceptance (docs/AEGIS_IMPLEMENTATION_PLAN.md Section 21): a seeded failing
run on the acceptance repo yields a FailureAnalysis that names the failing
assertion + the implicated function with evidence, fabricates no cause, and is
deterministic.
"""

from __future__ import annotations

from app.core.ids import new_id
from app.debugging import investigate as investigate_engine
from app.models.test_execution import TestExecution as ExecRow

_STDOUT = """\
=================================== FAILURES ===================================
______________________ test_discount_capped_at_50_percent ______________________

    def test_discount_capped_at_50_percent():
>       assert calculate_total(100.0, 0.9) == 50.0
E       assert 10.000000000000009 == 50.0
E        +  where 10.000000000000009 = calculate_total(100.0, 0.9)

test_invoice.py:9: AssertionError
=========================== short test summary info ============================
FAILED test_invoice.py::test_discount_capped_at_50_percent - assert 10.0 == 50.0
"""


def _analyzed_snapshot(db_session, ingestion_settings, acceptance_fixture_path) -> str:
    from app.analysis.analyze import analyze_snapshot
    from app.ingestion.ingest import ingest_repository
    from app.repository.repositories import RepositoryRepository
    from app.repository.snapshots import SnapshotRepository
    from app.schemas.repository import IngestRequest

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
    return snap.id


def _fake_execution(snapshot_id: str) -> ExecRow:
    return ExecRow(
        id=new_id(),
        task_id=new_id(),
        snapshot_id=snapshot_id,
        implementation_id=new_id(),
        version=1,
        command="pytest",
        exit_code=1,
        outcome="FAIL",
        results=[],
        reason=None,
        duration_ms=10,
    )


def test_failure_analysis_is_evidence_backed_and_deterministic(
    db_session, ingestion_settings, acceptance_fixture_path
):
    snapshot_id = _analyzed_snapshot(
        db_session, ingestion_settings, acceptance_fixture_path
    )
    execution = _fake_execution(snapshot_id)

    kwargs = dict(
        execution_row=execution,
        implementation_version=1,
        touched_paths={"invoice.py"},
        diff_text=(
            "diff --git a/invoice.py b/invoice.py\n"
            "@@ -8,1 +8,2 @@\n"
            "-    return price * (1 - discount)\n"
            "+    discount = min(discount, 0.5)\n"
            "+    return price * (1 - discount)\n"
        ),
        stdout_text=_STDOUT,
        stderr_text="",
        settings=ingestion_settings,
    )
    first = investigate_engine.run(db_session, **kwargs)
    second = investigate_engine.run(db_session, **kwargs)

    assert first.failure_records == second.failure_records
    assert first.facts == second.facts
    assert first.inferences == second.inferences
    assert first.classification == second.classification

    [record] = first.failure_records
    assert record["failure_type"] == "ASSERTION"
    assert "test_discount_capped_at_50_percent" in record["test_name"]
    assert first.classification["primary_symbol_id"] == "invoice.py::calculate_total"

    # evidence bundle: the diff hunk for the implicated file is carried
    assert any("invoice.py" in h for h in first.evidence["diff_hunks"])

    # no fabricated cause anywhere in the inferences
    for inf in first.inferences:
        assert "root cause" not in inf.lower()
        assert "caused by" not in inf.lower()

    # facts are concrete / re-checkable statements
    assert any("outcome = FAIL" in f for f in first.facts)
    assert any("calculate_total" in f for f in first.facts)
