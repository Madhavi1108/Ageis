"""Regression: the OpenAPI surface is pinned so a route is never dropped or
silently renamed. See docs/AEGIS_IMPLEMENTATION_PLAN.md Section 14
"Phase-wise testing" Regression bullet ("OpenAPI schema snapshot").

Asserts the (path, method) set rather than the full JSON blob -- the latter is
brittle across FastAPI/Pydantic versions, the former is the contract that
matters.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

EXPECTED_OPERATIONS = {
    ("/healthz", "get"),
    ("/version", "get"),
    ("/repositories", "post"),
    ("/repositories/{repository_id}", "get"),
    ("/repositories/{repository_id}/health", "get"),
    ("/repositories/{repository_id}/git/history", "get"),
    ("/repositories/{repository_id}/git/churn", "get"),
    ("/repositories/{repository_id}/git/blame", "get"),
    ("/repositories/{repository_id}/git/context", "get"),
    ("/repositories/{repository_id}/snapshots", "post"),
    ("/repositories/{repository_id}/snapshots/{snapshot_id}/analysis", "post"),
    ("/repositories/{repository_id}/snapshots/{snapshot_id}/analysis", "get"),
    ("/repositories/{repository_id}/snapshots/{snapshot_id}/analysis/graph", "get"),
    (
        "/repositories/{repository_id}/snapshots/{snapshot_id}/analysis/graph/subgraph",
        "get",
    ),
    (
        "/repositories/{repository_id}/snapshots/{snapshot_id}/analysis/graph/node/{node_id}",
        "get",
    ),
    ("/analysis/map", "post"),
    ("/tasks", "post"),
    ("/tasks", "get"),
    ("/tasks/{task_id}", "get"),
    ("/tasks/{task_id}/run", "post"),
    ("/tasks/{task_id}/cancel", "post"),
    ("/tasks/{task_id}/timeline", "get"),
    ("/tasks/{task_id}/mapping", "get"),
    ("/tasks/{task_id}/impact", "get"),
    ("/tasks/{task_id}/plan", "post"),
    ("/tasks/{task_id}/plan", "get"),
    ("/tasks/{task_id}/plan/validate", "post"),
    ("/tasks/{task_id}/changes", "post"),
    ("/tasks/{task_id}/changes", "get"),
    ("/tasks/{task_id}/tests", "post"),
    ("/tasks/{task_id}/tests", "get"),
    ("/tasks/{task_id}/executions", "post"),
    ("/tasks/{task_id}/executions", "get"),
    ("/tasks/{task_id}/failures", "get"),
    ("/tasks/{task_id}/repairs", "get"),
    ("/tasks/{task_id}/regression", "get"),
    ("/tasks/{task_id}/review", "get"),
    ("/tasks/{task_id}/confidence", "get"),
    ("/tasks/{task_id}/risk", "get"),
    ("/tasks/{task_id}/verification", "get"),
    ("/tasks/{task_id}/verification/decision", "post"),
    ("/tasks/{task_id}/pr", "post"),
    ("/tasks/{task_id}/pr", "get"),
    ("/tasks/{task_id}/memory", "get"),
    ("/executions/{execution_id}", "get"),
    ("/memory", "get"),
    ("/memory/search", "post"),
    ("/jobs", "get"),
    ("/jobs/{job_id}", "get"),
    ("/jobs/{job_id}/cancel", "post"),
    ("/github/repos/{owner}/{repo}", "get"),
    ("/github/repos/{owner}/{repo}/issues/{number}", "get"),
    ("/github/repos/{owner}/{repo}/issues/{number}/import", "post"),
    ("/reports/import", "post"),
    ("/reports/tasks/{task_id}", "get"),
    ("/reports/tasks/{task_id}.xlsx", "get"),
    ("/reports/metrics.xlsx", "get"),
}


def _operations() -> set[tuple[str, str]]:
    spec = TestClient(app).get("/openapi.json").json()
    return {
        (path, method) for path, methods in spec["paths"].items() for method in methods
    }


def test_openapi_surface_matches_snapshot():
    assert _operations() == EXPECTED_OPERATIONS


def test_all_task_routes_are_present():
    task_ops = {op for op in _operations() if op[0].startswith("/tasks")}
    assert task_ops == {
        ("/tasks", "post"),
        ("/tasks", "get"),
        ("/tasks/{task_id}", "get"),
        ("/tasks/{task_id}/run", "post"),
        ("/tasks/{task_id}/cancel", "post"),
        ("/tasks/{task_id}/timeline", "get"),
        ("/tasks/{task_id}/mapping", "get"),
        ("/tasks/{task_id}/impact", "get"),
        ("/tasks/{task_id}/plan", "post"),
        ("/tasks/{task_id}/plan", "get"),
        ("/tasks/{task_id}/plan/validate", "post"),
        ("/tasks/{task_id}/changes", "post"),
        ("/tasks/{task_id}/changes", "get"),
        ("/tasks/{task_id}/tests", "post"),
        ("/tasks/{task_id}/tests", "get"),
        ("/tasks/{task_id}/executions", "post"),
        ("/tasks/{task_id}/executions", "get"),
        ("/tasks/{task_id}/failures", "get"),
        ("/tasks/{task_id}/repairs", "get"),
        ("/tasks/{task_id}/regression", "get"),
        ("/tasks/{task_id}/review", "get"),
        ("/tasks/{task_id}/confidence", "get"),
        ("/tasks/{task_id}/risk", "get"),
        ("/tasks/{task_id}/verification", "get"),
        ("/tasks/{task_id}/verification/decision", "post"),
        ("/tasks/{task_id}/pr", "post"),
        ("/tasks/{task_id}/pr", "get"),
        ("/tasks/{task_id}/memory", "get"),
    }
