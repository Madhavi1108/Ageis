"""Liveness, readiness, build-metadata, and a lightweight metrics snapshot.

See docs/AEGIS_IMPLEMENTATION_PLAN.md Section 10 (liveness) and Section 35 /
docs/EXECUTION_MODEL.md Section 9 (readiness + metrics). ``/metrics`` here is a
cheap in-process signal (queue depth, circuit-breaker states, job counts) --
not a Prometheus/OpenMetrics endpoint and not a substitute for a real metrics
backend.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core import circuit_breaker
from app.db.session import get_db
from app.models.job import JobState
from app.orchestration import job_queue
from app.repository.jobs import JobRepository
from app.version import get_version_info

router = APIRouter(tags=["health"])


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
def readyz(db: Session = Depends(get_db)) -> JSONResponse:
    """Ready to serve traffic: the database answers a trivial query. Returns
    503 (not an exception) when it does not, so a load balancer can drain the
    instance without the error handler dressing it up as an application fault."""
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 -- any failure means "not ready"
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "reason": f"database: {exc}"[:200]},
        )
    return JSONResponse(status_code=200, content={"status": "ready"})


@router.get("/metrics")
def metrics(db: Session = Depends(get_db)) -> dict[str, object]:
    """A small operational snapshot (Phase 27). Intentionally unauthenticated
    and cheap, like ``/healthz``."""
    jobs = JobRepository(db)
    return {
        "queue_depth": job_queue.queue_depth(db),
        "jobs": {state.value: jobs.count(state=state.value) for state in JobState},
        "circuit_breakers": circuit_breaker.all_breakers(),
    }


@router.get("/version")
def version() -> dict[str, str | None]:
    return get_version_info()
