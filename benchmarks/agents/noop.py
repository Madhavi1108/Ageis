"""The default reference agent: does nothing.

With only ``NoopReferenceAgent`` configured, metric #15 is reported as
``N/A -- no reference agents configured`` (the Noop's outcomes are never a
real baseline and are excluded from the delta).
"""

from __future__ import annotations

from pathlib import Path

from benchmarks.schema import BenchmarkTask


class NoopReferenceAgent:
    name = "noop"
    is_baseline = False

    def solve(self, task: BenchmarkTask, workdir: Path) -> bool:  # noqa: ARG002
        return False
