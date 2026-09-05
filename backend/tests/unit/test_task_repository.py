"""Unit tests for TaskRepository / TaskStepRepository. Mirrors test_job_repository.py:
own throwaway SQLite engine, no FastAPI.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.repository import Repository
from app.repository.task_steps import TaskStepRepository
from app.repository.tasks import TaskRepository


@pytest.fixture
def session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    db = SessionLocal()
    yield db
    db.close()


@pytest.fixture
def repo_id(session):
    row = Repository(source_type="LOCAL", url_or_path="/tmp/x", name="x")
    session.add(row)
    session.commit()
    session.refresh(row)
    return row.id


def _make(session, repo_id, *, key, **kw):
    return TaskRepository(session).create(
        repository_id=repo_id,
        task_type=kw.get("task_type", "BUG"),
        title=kw.get("title", "t"),
        description_sanitized=kw.get("description_sanitized", "d"),
        idempotency_key=key,
        priority=kw.get("priority", "NORMAL"),
    )


def test_create_and_get_roundtrip(session, repo_id):
    created = _make(session, repo_id, key="k1")
    assert created.id
    assert created.state == "PENDING"
    assert TaskRepository(session).get(created.id).idempotency_key == "k1"


def test_get_by_idempotency_key_is_repo_scoped(session, repo_id):
    _make(session, repo_id, key="dup")
    found = TaskRepository(session).get_by_idempotency_key(repo_id, "dup")
    assert found is not None
    assert TaskRepository(session).get_by_idempotency_key("other-repo", "dup") is None


def test_list_filters_and_paginates(session, repo_id):
    _make(session, repo_id, key="a", task_type="BUG")
    _make(session, repo_id, key="b", task_type="FEATURE")
    _make(session, repo_id, key="c", task_type="BUG")
    tr = TaskRepository(session)

    assert len(tr.list(repository_id=repo_id)) == 3
    assert tr.count(repository_id=repo_id) == 3
    assert {t.task_type for t in tr.list(task_type="BUG")} == {"BUG"}
    assert tr.count(task_type="BUG") == 2

    page1 = tr.list(repository_id=repo_id, limit=2, offset=0)
    page2 = tr.list(repository_id=repo_id, limit=2, offset=2)
    assert len(page1) == 2 and len(page2) == 1
    assert {t.id for t in page1}.isdisjoint({t.id for t in page2})


def test_set_state_writes_state_and_terminal_reason(session, repo_id):
    task = _make(session, repo_id, key="s")
    TaskRepository(session).set_state(task.id, "QUEUED")
    assert TaskRepository(session).get(task.id).state == "QUEUED"
    TaskRepository(session).set_state(task.id, "CANCELLED", terminal_reason="stop")
    reloaded = TaskRepository(session).get(task.id)
    assert reloaded.state == "CANCELLED"
    assert reloaded.terminal_reason == "stop"


def test_task_step_seq_increments_and_close_current(session, repo_id):
    task = _make(session, repo_id, key="steps")
    steps = TaskStepRepository(session)

    s1 = steps.append(task_id=task.id, state="PENDING", agent="ingest")
    assert s1.seq == 1

    closed = steps.close_current(task.id)
    assert closed.seq == 1
    assert closed.exited_at is not None
    assert closed.duration_ms is not None and closed.duration_ms >= 0

    s2 = steps.append(task_id=task.id, state="QUEUED", agent="orchestrator")
    assert s2.seq == 2

    listed = steps.list_for_task(task.id)
    assert [s.seq for s in listed] == [1, 2]
    assert [s.state for s in listed] == ["PENDING", "QUEUED"]


def test_close_current_noop_when_no_open_step(session, repo_id):
    task = _make(session, repo_id, key="noop")
    assert TaskStepRepository(session).close_current(task.id) is None
