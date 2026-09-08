"""The reference-agent interface (docs/EVAL_HARNESS.md Section 4)."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from benchmarks.schema import BenchmarkTask


@runtime_checkable
class ReferenceAgent(Protocol):
    #: short stable identifier used as the column name in the report
    name: str

    def solve(self, task: BenchmarkTask, workdir: Path) -> bool:
        """Attempt ``task`` in ``workdir`` (a materialized copy of the repo).

        Mutate the files in place to apply the agent's patch. Return ``True`` if
        the agent produced a change, ``False`` if it declined / errored. The
        runner then evaluates ``fail_to_pass`` / ``pass_to_pass`` in ``workdir``
        exactly as it does for AEGIS, so the comparison is apples-to-apples.
        """
        ...
