"""Asyncio job worker (Phase 21, docs/AEGIS_IMPLEMENTATION_PLAN.md Section 29).

Claims ``RUN_TASK`` jobs (FIFO, deduped), runs the Orchestrator in a worker
thread on its own DB session, honours a concurrency cap, checkpoints progress,
retries with exponential backoff, and reclaims jobs orphaned by a crashed
worker (resume from ``last_checkpoint``). ``run_once`` is the synchronous unit
used by tests; ``run_forever`` is the process entrypoint.
"""

from __future__ import annotations

import asyncio
import logging
import os
import socket

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
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
        self._sem = asyncio.Semaphore(settings.worker_max_concurrency)
        self._stop = asyncio.Event()

    # ---- synchronous unit (tests / one poll cycle) ------------------- #

    def run_once(self, db, *, provider=None) -> str | None:
        job_queue.reclaim_orphans(db, stale_after_s=self._settings.worker_stale_after_s)
        job = job_queue.claim_next(db, worker_id=self._worker_id)
        if job is None:
            return None
        self._run_job(db, job, provider=provider)
        return job.id

    def _run_job(self, db, job, *, provider=None) -> None:
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
            delay = job_queue.retry_or_fail(
                db,
                job.id,
                error={"code": "ORCHESTRATION_FAILED", "message": str(exc)[:512]},
                backoff_base_s=self._settings.job_backoff_base_s,
            )
            _logger.warning(
                "job %s failed (retry in %ss)", job.id, delay, exc_info=True
            )
            return
        JobRepository(db).mark_succeeded(job.id)

    # ---- async loop (process entrypoint) --------------------------- #

    def stop(self) -> None:
        self._stop.set()

    async def run_forever(self) -> None:
        loop = asyncio.get_running_loop()
        _logger.info("orchestration worker %s started", self._worker_id)
        while not self._stop.is_set():
            async with self._sem:
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
