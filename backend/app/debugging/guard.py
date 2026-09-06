"""Repair-loop guards: budgets, no-progress detection, candidate scoring
(docs/AEGIS_IMPLEMENTATION_PLAN.md Section 22).

All pure functions / value objects -- the loop controller (repair_loop.py)
composes them. Deterministic: the same runs in the same order always score and
terminate identically.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from app.schemas.execution import TestExecutionRun


@dataclass(frozen=True)
class LoopBudget:
    max_iterations: int
    wall_clock_s: float
    started_at: float

    @classmethod
    def start(cls, *, max_iterations: int, wall_clock_s: float) -> "LoopBudget":
        return cls(max_iterations, wall_clock_s, time.monotonic())

    def iteration_exhausted(self, next_iteration: int) -> bool:
        return next_iteration > self.max_iterations

    def wall_clock_exhausted(self, *, now: float | None = None) -> bool:
        current = time.monotonic() if now is None else now
        return (current - self.started_at) >= self.wall_clock_s


def failure_signature(run: TestExecutionRun) -> str:
    """A stable, order-independent fingerprint of *what failed* -- two runs with
    the same failing test set + outcome have the same signature."""
    failed = ",".join(sorted(run.failed_ids()))
    return f"{run.outcome}|{failed}"


def no_progress(signatures: list[str]) -> bool:
    """True once the last two recorded failure signatures are identical -- the
    loop is not moving and should stop (Section 22: "the same failure signature
    twice aborts the loop")."""
    return len(signatures) >= 2 and signatures[-1] == signatures[-2]


def score(
    run: TestExecutionRun, *, regression_failures: int, diff_size: int
) -> tuple[int, int, int]:
    """Lexicographic candidate score, lower is better:
    (failing targeted tests, regression failures, diff size)."""
    return (len(run.failed_ids()), regression_failures, diff_size)
