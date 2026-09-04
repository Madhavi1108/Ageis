"""Minimal scratch-SQLite artifact store. See
docs/AEGIS_IMPLEMENTATION_PLAN.md Phase 1 deliverables: "no job queue, no
worker, no DB beyond a scratch SQLite for artifacts." The real Artifact
model (docs/DATA_MODEL.md Section 2.5) arrives with Phase 21.
"""
from __future__ import annotations

import sqlite3
import time
import uuid
from pathlib import Path

from aegis.schemas.trust_report import TrustReportV0

DEFAULT_DB_PATH = Path(".aegis") / "runs.db"


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS runs (
            id TEXT PRIMARY KEY,
            repo TEXT NOT NULL,
            task_title TEXT NOT NULL,
            outcome TEXT NOT NULL,
            trust_report_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    return conn


def record_run(
    *, repo: str, trust_report: TrustReportV0, db_path: Path = DEFAULT_DB_PATH
) -> str:
    """Insert one run row and return its id. Never raises on a DB error to
    the caller's core logic path -- this is a scratch log, not the source of
    truth (the returned TrustReportV0 is)."""
    run_id = str(uuid.uuid4())
    try:
        conn = _connect(db_path)
        with conn:
            conn.execute(
                "INSERT INTO runs (id, repo, task_title, outcome, trust_report_json, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    repo,
                    trust_report.task_title,
                    trust_report.outcome,
                    trust_report.model_dump_json(),
                    time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                ),
            )
        conn.close()
    except sqlite3.Error:
        pass  # scratch log only; never let this fail the pipeline
    return run_id
