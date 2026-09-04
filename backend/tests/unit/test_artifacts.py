import json

from aegis.artifacts import record_run
from aegis.schemas.trust_report import EvidenceTrace, TrustReportV0


def test_record_run_writes_a_readable_row(tmp_path):
    db_path = tmp_path / "runs.db"
    report = TrustReportV0(
        task_repo="repo",
        task_title="title",
        outcome="VERIFIED",
        evidence_trace=EvidenceTrace(why_safe="ok"),
    )
    run_id = record_run(repo="repo", trust_report=report, db_path=db_path)

    assert db_path.exists()
    import sqlite3

    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT id, repo, outcome, trust_report_json FROM runs WHERE id = ?", (run_id,)
    ).fetchone()
    conn.close()

    assert row is not None
    assert row[0] == run_id
    assert row[1] == "repo"
    assert row[2] == "VERIFIED"
    assert json.loads(row[3])["task_title"] == "title"
