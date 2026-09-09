"""In-process circuit breaker for outbound calls (Phase 27,
docs/AEGIS_IMPLEMENTATION_PLAN.md §35, docs/EXECUTION_MODEL.md).

Wraps the AI provider and the GitHub client. After ``fail_threshold`` consecutive
failures the breaker OPENs and every call fails fast with
``UpstreamUnavailableError`` (so the job's retry/backoff handles it) instead of
burning each call's own retry budget against a dead upstream. After
``reset_after_s`` it goes HALF_OPEN and lets one probe through: success -> CLOSED,
failure -> OPEN again.

Single-process worker + FastAPI app, so a plain lock-guarded counter is enough;
a distributed deployment would move this to a shared store (documented follow-up).
"""

from __future__ import annotations

import threading
import time
from typing import Callable, TypeVar

from fastapi import status

from app.core.errors import AppError

T = TypeVar("T")

CLOSED = "CLOSED"
OPEN = "OPEN"
HALF_OPEN = "HALF_OPEN"


class UpstreamUnavailableError(AppError):
    """An outbound dependency's circuit breaker is OPEN -- fail fast."""

    def __init__(self, name: str, *, retry_after_s: float) -> None:
        super().__init__(
            "UPSTREAM_UNAVAILABLE",
            f"{name} is temporarily unavailable (circuit open)",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details={"upstream": name, "retry_after_s": round(retry_after_s, 1)},
        )
        self.name = name
        self.retry_after_s = retry_after_s


class CircuitBreaker:
    def __init__(
        self,
        name: str,
        *,
        fail_threshold: int = 5,
        reset_after_s: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.name = name
        self._fail_threshold = max(1, fail_threshold)
        self._reset_after_s = reset_after_s
        self._clock = clock
        self._lock = threading.Lock()
        self._failures = 0
        self._opened_at: float | None = None

    @property
    def state(self) -> str:
        with self._lock:
            return self._state_locked()

    def _state_locked(self) -> str:
        if self._opened_at is None:
            return CLOSED
        if self._clock() - self._opened_at >= self._reset_after_s:
            return HALF_OPEN
        return OPEN

    def _before(self) -> None:
        with self._lock:
            st = self._state_locked()
            if st == OPEN:
                remaining = self._reset_after_s - (self._clock() - (self._opened_at or 0))
                raise UpstreamUnavailableError(self.name, retry_after_s=max(0.0, remaining))
            # CLOSED or HALF_OPEN -> allow the call (HALF_OPEN lets one probe through)

    def _on_success(self) -> None:
        with self._lock:
            self._failures = 0
            self._opened_at = None

    def _on_failure(self) -> None:
        with self._lock:
            self._failures += 1
            if self._failures >= self._fail_threshold or self._state_locked() == HALF_OPEN:
                self._opened_at = self._clock()

    def call(
        self,
        fn: Callable[..., T],
        *args: object,
        ignore: tuple[type[BaseException], ...] = (),
        **kwargs: object,
    ) -> T:
        """Run ``fn(*args, **kwargs)`` through the breaker. An
        ``UpstreamUnavailableError`` from a fast-fail is re-raised as-is and does
        not itself count as an upstream failure. Exception types listed in
        ``ignore`` (e.g. a 404 / auth error that a retry cannot fix) propagate
        without tripping the breaker -- only "upstream is unhealthy" failures
        should move it toward OPEN."""
        self._before()
        try:
            result = fn(*args, **kwargs)
        except UpstreamUnavailableError:
            raise
        except ignore:
            raise
        except Exception:
            self._on_failure()
            raise
        self._on_success()
        return result

    # test / metrics helpers
    def reset(self) -> None:
        with self._lock:
            self._failures = 0
            self._opened_at = None

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                "name": self.name,
                "state": self._state_locked(),
                "consecutive_failures": self._failures,
            }


# --------------------------------------------------------------------------- #
# Process-wide registry (so /metrics can list open breakers)
# --------------------------------------------------------------------------- #

_REGISTRY: dict[str, CircuitBreaker] = {}
_REGISTRY_LOCK = threading.Lock()


def get_breaker(
    name: str, *, fail_threshold: int = 5, reset_after_s: float = 30.0
) -> CircuitBreaker:
    with _REGISTRY_LOCK:
        cb = _REGISTRY.get(name)
        if cb is None:
            cb = CircuitBreaker(
                name, fail_threshold=fail_threshold, reset_after_s=reset_after_s
            )
            _REGISTRY[name] = cb
        return cb


def all_breakers() -> list[dict[str, object]]:
    with _REGISTRY_LOCK:
        return [cb.snapshot() for cb in _REGISTRY.values()]


def reset_all() -> None:
    """Test hook."""
    with _REGISTRY_LOCK:
        for cb in _REGISTRY.values():
            cb.reset()
