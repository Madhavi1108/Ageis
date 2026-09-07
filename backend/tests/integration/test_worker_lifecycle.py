"""Phase 21 integration: the worker claims a RUN_TASK job and runs the
orchestrator to a terminal state; cooperative cancel; crash-recovery resume.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models.job import JobState
from app.models.task import TaskState
from app.orchestration import job_queue
from app.orchestration.worker import OrchestrationWorker
from app.repository.jobs import JobRepository
from app.repository.tasks import TaskRepository
from app.services import verification as verification_service

from tests.integration.test_orchestrator_pipeline import _fake_settings, _seed


def _worker(settings, db):
    return OrchestrationWorker(settings, session_factory=lambda: db)


def _finish(db, settings, task_id) -> str:
    task = TaskRepository(db).get(task_id)
    if task.state == TaskState.AWAITING_APPROVAL.value:
        verification_service.resolve_decision(
            db, settings=settings, task_id=task_id,
            decision="APPROVE", reason="ok", actor="a@x",
        )
    return TaskRepository(db).get(task_id).state


def test_run_then_worker_completes(db_session, tmp_path, acceptance_fixture_path):
    settings = _fake_settings(tmp_path, acceptance_fixture_path.parent)
    task_id, provider = _seed(db_session, settings, acceptance_fixture_path)

    job = job_queue.enqueue_run(db_session, task_id)
    assert job.state == JobState.QUEUED.value

    handled = _worker(settings, db_session).run_once(db_session, provider=provider)
    assert handled == job.id
    assert _finish(db_session, settings, task_id) == TaskState.COMPLETED.value
    fresh = JobRepository(db_session).get(job.id)
    assert fresh.state == JobState.SUCCEEDED.value
    assert fresh.last_checkpoint and fresh.last_checkpoint["stage"] == "verify"


def test_cooperative_cancel_between_stages(
    db_session, tmp_path, acceptance_fixture_path, monkeypatch
):
    settings = _fake_settings(tmp_path, acceptance_fixture_path.parent)
    task_id, provider = _seed(db_session, settings, acceptance_fixture_path)

    from app.orchestration import orchestrator as orch

    real_impl = orch.implementation_service.generate_implementation

    def _impl_then_cancel(db, **kw):
        out = real_impl(db, **kw)
        TaskRepository(db).set_cancel_requested(task_id, True)
        return out

    monkeypatch.setattr(
        orch.implementation_service, "generate_implementation", _impl_then_cancel
    )

    task = orch.run_task(
        db_session, settings=settings, task_id=task_id, provider=provider
    )
    assert task.state == TaskState.CANCELLED.value
    assert task.terminal_reason and "cancelled during" in task.terminal_reason
    # a terminal CANCELLED orchestrator step was appended and it is the last one
    from app.repository.task_steps import TaskStepRepository

    steps = TaskStepRepository(db_session).list_for_task(task_id)
    assert steps[-1].state == TaskState.CANCELLED.value
    assert steps[-1].agent == "orchestrator"
    # the pipeline stopped before verification
    from app.repository.verifications import VerificationRepository

    assert VerificationRepository(db_session).get_by_task(task_id) is None


def test_orphan_job_is_reclaimed_and_resumed(
    db_session, tmp_path, acceptance_fixture_path
):
    settings = _fake_settings(tmp_path, acceptance_fixture_path.parent)
    task_id, provider = _seed(db_session, settings, acceptance_fixture_path)

    job = job_queue.enqueue_run(db_session, task_id)
    jobs = JobRepository(db_session)
    jobs.mark_running(job.id)
    jobs.set_checkpoint(job.id, {"stage": "analyze", "state": "ANALYZING"})
    stale = jobs.get(job.id)
    stale.started_at = datetime.now(timezone.utc) - timedelta(hours=2)
    db_session.commit()

    # a fresh worker poll reclaims the orphan and finishes it
    handled = _worker(settings, db_session).run_once(db_session, provider=provider)
    assert handled == job.id
    assert _finish(db_session, settings, task_id) == TaskState.COMPLETED.value
