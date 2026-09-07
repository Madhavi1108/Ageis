"""Phase 21 unit: the guarded §4.3 transition table."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.task import Task, TaskState
from app.orchestration import state_machine as sm
from app.orchestration.errors import IllegalStateTransitionError
from app.repository.task_steps import TaskStepRepository

_LEGAL = [
    ("PENDING", "QUEUED"),
    ("QUEUED", "INGESTING"),
    ("INGESTING", "ANALYZING"),
    ("INGESTING", "PARTIALLY_SUPPORTED"),
    ("ANALYZING", "PLANNING"),
    ("PLANNING", "PLAN_VALIDATION"),
    ("PLAN_VALIDATION", "IMPLEMENTING"),
    ("PLAN_VALIDATION", "PLANNING"),
    ("PLAN_VALIDATION", "AWAITING_APPROVAL"),
    ("IMPLEMENTING", "GENERATING_TESTS"),
    ("GENERATING_TESTS", "EXECUTING_TESTS"),
    ("EXECUTING_TESTS", "REGRESSION_TESTING"),
    ("EXECUTING_TESTS", "INVESTIGATING"),
    ("INVESTIGATING", "REPAIRING"),
    ("REPAIRING", "EXECUTING_TESTS"),
    ("REPAIRING", "REGRESSION_TESTING"),
    ("REGRESSION_TESTING", "REVIEWING"),
    ("REGRESSION_TESTING", "INVESTIGATING"),
    ("REVIEWING", "VERIFYING"),
    ("VERIFYING", "COMPLETED"),
    ("VERIFYING", "AWAITING_APPROVAL"),
    ("AWAITING_APPROVAL", "COMPLETED"),
    ("AWAITING_APPROVAL", "VERIFYING"),
]
_ILLEGAL = [
    ("PENDING", "IMPLEMENTING"),
    ("QUEUED", "PLANNING"),
    ("REVIEWING", "PLANNING"),
    ("IMPLEMENTING", "EXECUTING_TESTS"),
    ("COMPLETED", "VERIFYING"),
    ("FAILED", "PLANNING"),
    ("VERIFYING", "REVIEWING"),
]


@pytest.mark.parametrize("frm,to", _LEGAL)
def test_legal_transitions_pass(frm, to):
    sm.assert_transition(frm, to)
    assert sm.can_transition(frm, to)


@pytest.mark.parametrize("frm,to", _ILLEGAL)
def test_illegal_transitions_raise(frm, to):
    assert not sm.can_transition(frm, to)
    with pytest.raises(IllegalStateTransitionError):
        sm.assert_transition(frm, to)


def test_self_loop_and_terminal():
    assert sm.can_transition("PLANNING", "PLANNING")  # idempotent stage re-run
    assert not sm.can_transition("COMPLETED", "FAILED")
    assert "PARTIALLY_SUPPORTED" in sm.TERMINAL


def test_every_source_state_can_be_cancelled():
    for frm, tos in sm.TRANSITIONS.items():
        assert "CANCELLED" in tos, frm
    # every working state (past QUEUED) can fail
    for frm in ("INGESTING", "PLANNING", "IMPLEMENTING", "EXECUTING_TESTS", "VERIFYING"):
        assert "FAILED" in sm.TRANSITIONS[frm], frm


def _session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def test_transition_closes_prior_step_and_links_refs():
    db = _session()
    task = Task(
        repository_id="r1",
        task_type="BUG",
        title="t",
        description_sanitized="d",
        idempotency_key="k1",
        state=TaskState.QUEUED.value,
    )
    db.add(task)
    db.commit()
    steps = TaskStepRepository(db)
    steps.append(task_id=task.id, state="QUEUED", agent="api")

    sm.transition(db, task.id, "INGESTING", agent="orchestrator", output_ref="snap-1")
    sm.transition(
        db, task.id, "ANALYZING", agent="orchestrator", input_ref="snap-1",
        output_ref="map-1",
    )

    rows = steps.list_for_task(task.id)
    assert [r.state for r in rows] == ["QUEUED", "INGESTING", "ANALYZING"]
    assert rows[0].exited_at is not None  # QUEUED step was closed
    assert rows[1].exited_at is not None  # INGESTING step was closed by the 2nd transition
    assert rows[2].input_ref == "snap-1"
    assert rows[2].agent == "orchestrator"
    db.refresh(task)
    assert task.state == "ANALYZING"
