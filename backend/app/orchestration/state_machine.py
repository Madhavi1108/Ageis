"""The guarded §4.3 workflow state machine
(docs/AEGIS_IMPLEMENTATION_PLAN.md Section 4.3).

``transition`` is the single writer for orchestrated state changes: it enforces
the table, closes the currently-open ``TaskStep``, sets ``Task.state``, and
appends a new step linked to the prior stage's output (``input_ref`` /
``output_ref``) -- so the timeline is a connected, guarded chain.

The per-stage manual API endpoints keep their lenient ``set_state``; the guard
applies to the orchestrator path (every stage service's own ``set_state`` write
is a §4.3-legal self-loop when re-run underneath the orchestrator).
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.task import Task, TaskState
from app.orchestration.errors import IllegalStateTransitionError
from app.repository.task_steps import TaskStepRepository
from app.repository.tasks import TaskRepository

S = TaskState

TRANSITIONS: dict[str, frozenset[str]] = {
    S.PENDING.value: frozenset({S.QUEUED.value, S.CANCELLED.value}),
    S.QUEUED.value: frozenset({S.INGESTING.value, S.CANCELLED.value}),
    S.INGESTING.value: frozenset(
        {S.ANALYZING.value, S.FAILED.value, S.PARTIALLY_SUPPORTED.value, S.CANCELLED.value}
    ),
    S.ANALYZING.value: frozenset(
        {S.PLANNING.value, S.FAILED.value, S.PARTIALLY_SUPPORTED.value, S.CANCELLED.value}
    ),
    S.PLANNING.value: frozenset(
        {S.PLAN_VALIDATION.value, S.FAILED.value, S.CANCELLED.value}
    ),
    S.PLAN_VALIDATION.value: frozenset(
        {
            S.IMPLEMENTING.value,
            S.PLANNING.value,
            S.FAILED.value,
            S.AWAITING_APPROVAL.value,
            S.CANCELLED.value,
        }
    ),
    S.IMPLEMENTING.value: frozenset(
        {S.GENERATING_TESTS.value, S.FAILED.value, S.CANCELLED.value}
    ),
    S.GENERATING_TESTS.value: frozenset(
        {S.EXECUTING_TESTS.value, S.FAILED.value, S.CANCELLED.value}
    ),
    S.EXECUTING_TESTS.value: frozenset(
        {
            S.REGRESSION_TESTING.value,
            S.INVESTIGATING.value,
            S.FAILED.value,
            S.CANCELLED.value,
        }
    ),
    S.INVESTIGATING.value: frozenset(
        {S.REPAIRING.value, S.FAILED.value, S.CANCELLED.value}
    ),
    S.REPAIRING.value: frozenset(
        {
            S.EXECUTING_TESTS.value,
            S.REGRESSION_TESTING.value,
            S.FAILED.value,
            S.CANCELLED.value,
        }
    ),
    S.REGRESSION_TESTING.value: frozenset(
        {S.REVIEWING.value, S.INVESTIGATING.value, S.FAILED.value, S.CANCELLED.value}
    ),
    S.REVIEWING.value: frozenset(
        {S.VERIFYING.value, S.FAILED.value, S.CANCELLED.value}
    ),
    S.VERIFYING.value: frozenset(
        {
            S.COMPLETED.value,
            S.AWAITING_APPROVAL.value,
            S.FAILED.value,
            S.CANCELLED.value,
        }
    ),
    S.AWAITING_APPROVAL.value: frozenset(
        {S.VERIFYING.value, S.COMPLETED.value, S.CANCELLED.value, S.FAILED.value}
    ),
}

TERMINAL: frozenset[str] = frozenset(
    {
        S.COMPLETED.value,
        S.FAILED.value,
        S.CANCELLED.value,
        S.PARTIALLY_SUPPORTED.value,
    }
)


def can_transition(frm: str, to: str) -> bool:
    if frm == to:
        return True  # idempotent stage re-run
    if frm in TERMINAL:
        return False
    return to in TRANSITIONS.get(frm, frozenset())


def assert_transition(frm: str, to: str) -> None:
    if not can_transition(frm, to):
        raise IllegalStateTransitionError(frm, to)


def transition(
    db: Session,
    task_id: str,
    to_state: str,
    *,
    agent: str,
    terminal_reason: str | None = None,
    input_ref: str | None = None,
    output_ref: str | None = None,
) -> Task:
    tasks = TaskRepository(db)
    task = tasks.get(task_id)
    assert task is not None
    assert_transition(task.state, to_state)

    steps = TaskStepRepository(db)
    steps.close_current(task_id)
    updated = tasks.set_state(task_id, to_state, terminal_reason=terminal_reason)
    steps.append(
        task_id=task_id,
        state=to_state,
        agent=agent,
        input_ref=input_ref,
        output_ref=output_ref,
    )
    return updated
