"""Sandbox resource-limit defaults. See docs/EXECUTION_MODEL.md Section 5 and
docs/DECISIONS/ADR-0010."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ResourceLimits:
    cpus: float = 2.0
    memory_mb: int = 2048
    pids_limit: int = 512
    nofile_limit: int = 4096
    nproc_limit: int = 512
    wall_clock_s: int = 600
