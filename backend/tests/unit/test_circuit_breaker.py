"""Phase 27 unit: the in-process circuit breaker state machine."""

from __future__ import annotations

import pytest

from app.core.circuit_breaker import (
    CLOSED,
    HALF_OPEN,
    OPEN,
    CircuitBreaker,
    UpstreamUnavailableError,
    all_breakers,
    get_breaker,
    reset_all,
)


class _Clock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


def _boom() -> None:
    raise RuntimeError("upstream is down")


def test_opens_after_threshold_consecutive_failures():
    cb = CircuitBreaker("x", fail_threshold=3, reset_after_s=10.0, clock=_Clock())
    for _ in range(2):
        with pytest.raises(RuntimeError):
            cb.call(_boom)
    assert cb.state == CLOSED  # 2 < 3
    with pytest.raises(RuntimeError):
        cb.call(_boom)
    assert cb.state == OPEN


def test_open_breaker_fast_fails_without_calling_fn():
    cb = CircuitBreaker("x", fail_threshold=1, reset_after_s=10.0, clock=_Clock())
    with pytest.raises(RuntimeError):
        cb.call(_boom)
    assert cb.state == OPEN

    calls = []
    with pytest.raises(UpstreamUnavailableError) as ei:
        cb.call(lambda: calls.append(1))
    assert calls == []  # fn never ran
    assert ei.value.details["upstream"] == "x"


def test_half_open_after_reset_then_success_closes():
    clock = _Clock()
    cb = CircuitBreaker("x", fail_threshold=1, reset_after_s=10.0, clock=clock)
    with pytest.raises(RuntimeError):
        cb.call(_boom)
    assert cb.state == OPEN

    clock.t = 10.0
    assert cb.state == HALF_OPEN
    assert cb.call(lambda: "ok") == "ok"
    assert cb.state == CLOSED


def test_half_open_failure_reopens():
    clock = _Clock()
    cb = CircuitBreaker("x", fail_threshold=1, reset_after_s=5.0, clock=clock)
    with pytest.raises(RuntimeError):
        cb.call(_boom)
    clock.t = 5.0
    assert cb.state == HALF_OPEN
    with pytest.raises(RuntimeError):
        cb.call(_boom)
    assert cb.state == OPEN
    # the probe failure re-stamped opened_at -> still OPEN just after
    clock.t = 9.0
    assert cb.state == OPEN


def test_success_resets_failure_count():
    cb = CircuitBreaker("x", fail_threshold=3, reset_after_s=10.0, clock=_Clock())
    with pytest.raises(RuntimeError):
        cb.call(_boom)
    cb.call(lambda: "ok")
    with pytest.raises(RuntimeError):
        cb.call(_boom)
    with pytest.raises(RuntimeError):
        cb.call(_boom)
    assert cb.state == CLOSED  # counter was reset by the success in between


def test_ignored_exceptions_do_not_trip_the_breaker():
    cb = CircuitBreaker("x", fail_threshold=2, reset_after_s=10.0, clock=_Clock())

    class Ignored(Exception):
        pass

    for _ in range(5):
        with pytest.raises(Ignored):
            cb.call(_raise(Ignored), ignore=(Ignored,))
    assert cb.state == CLOSED
    assert cb.snapshot()["consecutive_failures"] == 0


def test_fast_fail_error_is_not_itself_a_failure():
    clock = _Clock()
    cb = CircuitBreaker("x", fail_threshold=1, reset_after_s=100.0, clock=clock)
    with pytest.raises(RuntimeError):
        cb.call(_boom)
    for _ in range(3):
        with pytest.raises(UpstreamUnavailableError):
            cb.call(lambda: "never")
    # still one real failure recorded, not four
    assert cb.snapshot()["consecutive_failures"] == 1


def _raise(exc_type):
    def _fn():
        raise exc_type("nope")

    return _fn


# --- process-wide registry ------------------------------------------------- #


def test_registry_get_breaker_is_idempotent_and_reset_all():
    reset_all()
    a = get_breaker("svc", fail_threshold=1, reset_after_s=1.0)
    b = get_breaker("svc")
    assert a is b
    with pytest.raises(RuntimeError):
        a.call(_boom)
    assert a.state == OPEN
    names = {row["name"] for row in all_breakers()}
    assert "svc" in names
    reset_all()
    assert a.state == CLOSED
