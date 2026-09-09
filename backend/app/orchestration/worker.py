"""Asyncio job worker (Phase 21, docs/AEGIS_IMPLEMENTATION_PLAN.md Section 29).

**Single sequential process** -- one job at a time (ADR-0003; a distributed /
parallel worker is a documented Phase 27 follow-up). Claims ``RUN_TASK`` and
``GC`` jobs (FIFO, deduped, honouring retry ``run_after``), runs the work on its
own DB session, checkpoints + heartbeats progress, retries retryable failures
with a real not-before backoff, and reclaims jobs orphaned by a crashed worker
(resume from ``last_checkpoint``). ``run_once`` is the synchronous unit used by
tests; ``run_forever`` is the process entrypoint.
"""

from __future__ import annotations

import asyncio
import logging
import os
import socket
import time

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.models.job import JobType
from app.orchestration import gc as gc_mod
from app.orchestration import job_queue, orchestrator
from app.repository.jobs import JobRepository

_logger = logging.getLogger("app.orchestration.worker")


def _worker_id() -> str:
    return f"{socket.gethostname()}:{os.getpid()}"


class OrchestrationWorker:
    def __init__(self, settings: Settings, *, session_factory) -> None:
        self._settings = settings
        self._session_factory = session_factory
        self._worker_id = _worker_id()
        self._stop = asyncio.Event()
        self._last_gc = 0.0  # monotonic stamp of the last GC enqueue

    # ---- synchronous unit (tests / one poll cycle) ------------------- #

    def run_once(self, db, *, provider=None) -> str | None:
        job_queue.reclaim_orphans(db, stale_after_s=self._settings.worker_stale_after_s)
        self._maybe_enqueue_gc(db)
        job = job_queue.claim_next(db, worker_id=self._worker_id)
        if job is None:
            return None
        self._run_job(db, job, provider=provider)
        return job.id

    def _maybe_enqueue_gc(self, db) -> None:
        if not self._settings.gc_enabled:
            return
        now = time.monotonic()
        if self._last_gc and now - self._last_gc < self._settings.gc_interval_s:
            return
        self._last_gc = now
        from datetime import datetime, timezone

        bucket = datetime.now(timezone.utc).strftime("%Y%m%d%H")
        if job_queue.enqueue_gc(db, bucket=bucket) is not None:
            _logger.info("enqueued GC job for bucket %s", bucket)

    def _run_job(self, db, job, *, provider=None) -> None:
        if job.type == JobType.GC.value:
            self._run_gc_job(db, job)
            return
        resume_from = job_queue.resume_stage(job)
        try:
            orchestrator.run_task(
                db,
                settings=self._settings,
                task_id=job.task_id,
                provider=provider if provider is not None else orchestrator._RESOLVE_FROM_SETTINGS,
                job_id=job.id,
                resume_from=resume_from,
            )
        except Exception as exc:  # noqa: BLE001 -- retry/backoff decision
            code = getattr(exc, "code", None) or "ORCHESTRATION_FAILED"
            delay = job_queue.retry_or_fail(
                db,
                job.id,
                error={"code": code, "message": str(exc)[:512]},
                backoff_base_s=self._settings.job_backoff_base_s,
            )
            _logger.warning(
                "job %s failed (%s; %s)",
                job.id,
                code,
                f"retry in {delay:.1f}s" if delay is not None else "no retry",
                exc_info=True,
            )
            return
        JobRepository(db).mark_succeeded(job.id)

    def _run_gc_job(self, db, job) -> None:
        try:
            summary = gc_mod.run_gc(db, self._settings)
        except Exception as exc:  # noqa: BLE001
            job_queue.retry_or_fail(
                db,
                job.id,
                error={"code": "GC_FAILED", "message": str(exc)[:512]},
                backoff_base_s=self._settings.job_backoff_base_s,
            )
            _logger.warning("GC job %s failed", job.id, exc_info=True)
            return
        _logger.info("GC job %s: %s", job.id, summary)
        JobRepository(db).mark_succeeded(job.id)

    # ---- async loop (process entrypoint) --------------------------- #

    def stop(self) -> None:
        self._stop.set()

    async def run_forever(self) -> None:
        loop = asyncio.get_running_loop()
        _logger.info(
            "orchestration worker %s started (sequential; one job at a time)",
            self._worker_id,
        )
        while not self._stop.is_set():
            handled = await loop.run_in_executor(None, self._poll_once)
            if not handled:
                try:
                    await asyncio.wait_for(
                        self._stop.wait(), timeout=self._settings.worker_poll_interval_s
                    )
                except asyncio.TimeoutError:
                    pass

    def _poll_once(self) -> str | None:
        db = self._session_factory()
        try:
            return self.run_once(db)
        finally:
            db.close()


def build_worker(settings: Settings | None = None) -> OrchestrationWorker:
    settings = settings or get_settings()
    from app.db.session import SessionLocal

    return OrchestrationWorker(settings, session_factory=SessionLocal)


def main() -> None:
    settings = get_settings()
    configure_logging(settings)
    worker = build_worker(settings)
    try:
        asyncio.run(worker.run_forever())
    except KeyboardInterrupt:  # pragma: no cover
        worker.stop()


if __name__ == "__main__":  # pragma: no cover
    main()
