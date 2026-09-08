"""Sheet + column contracts for the import and export workbooks -- the single
source of truth the contract tests assert against.
"""

from __future__ import annotations

# --- import workbook -------------------------------------------------------

REPOSITORIES_SHEET = "Repositories"
TASKS_SHEET = "Tasks"

# (column name, required?)
REPOSITORIES_COLUMNS: list[tuple[str, bool]] = [
    ("source_type", True),  # LOCAL | GITHUB
    ("url_or_path", True),
    ("name", False),
    ("owner", False),
    ("default_branch", False),
]

TASKS_IMPORT_COLUMNS: list[tuple[str, bool]] = [
    ("repository_url_or_path", True),  # resolved to a repository_id at import time
    ("text", False),  # free-text issue body; provide this OR issue_title+issue_body
    ("issue_title", False),
    ("issue_body", False),
    ("issue_external_ref", False),
    ("title", False),
    ("task_type", False),  # BUG | FEATURE | REFACTOR | REQUIREMENT | QUESTION
    ("priority", False),  # LOW | NORMAL | HIGH
    ("allowed_paths", False),  # newline- or comma-separated globs
    ("created_by", False),
]


def required_columns(columns: list[tuple[str, bool]]) -> list[str]:
    return [name for name, req in columns if req]


def all_columns(columns: list[tuple[str, bool]]) -> list[str]:
    return [name for name, _ in columns]


# --- metrics / corpus export workbook ------------------------------------

EXPORT_SHEETS: dict[str, list[str]] = {
    "Tasks": [
        "task_id",
        "repository_id",
        "title",
        "task_type",
        "priority",
        "state",
        "terminal_reason",
        "created_at",
        "updated_at",
    ],
    "Execution Results": [
        "task_id",
        "execution_id",
        "version",
        "outcome",
        "exit_code",
        "passed",
        "failed",
        "total",
        "duration_ms",
        "reason",
    ],
    "Tests": [
        "task_id",
        "version",
        "name",
        "path",
        "target_symbol",
        "kind",
        "status",
        "invalid_reason",
    ],
    "Failures": [
        "task_id",
        "execution_id",
        "test_name",
        "failure_type",
        "exception_type",
        "message",
        "in_diff_frames",
    ],
    "Repairs": [
        "task_id",
        "outcome",
        "iteration",
        "attempt_outcome",
        "hypothesis",
        "failing_before",
        "failing_after",
        "regression_failures",
    ],
    "Reviews": [
        "task_id",
        "implementation_version",
        "blocking",
        "critical",
        "high",
        "medium",
        "low",
        "info",
        "static_tools_run",
    ],
    "Risk": [
        "task_id",
        "pcs_value",
        "pcs_class",
        "pcs_overall_confidence",
        "crs_value",
        "crs_class",
        "crs_overall_confidence",
        "hard_gate",
    ],
    "Verification": [
        "task_id",
        "verdict",
        "mandatory_pass",
        "mandatory_total",
        "replay_fidelity",
        "resulting_state",
        "decision",
        "model_version",
    ],
    "Engineering Metrics": [
        "num",
        "metric",
        "formula",
        "value",
        "basis",
        "source",
    ],
}

METRICS_SHEET = "Engineering Metrics"
