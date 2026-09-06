"""Scope guard: compares touched files against the plan's declared allowlist
and flags anything outside it (docs/AEGIS_IMPLEMENTATION_PLAN.md Section 18,
Absolute Rule 13). Ported from backend/aegis/implementation/scope_tracker.py.
"""

from __future__ import annotations

from pathlib import Path

from app.implementation.patcher import touched_paths
from app.implementation.workspace_rw import RWWorkspace


def unplanned_files(
    source_workspace: Path, ws: RWWorkspace, allowed: list[str]
) -> set[str]:
    """Files touched in ``ws`` relative to ``source_workspace`` that are not
    in the plan's allowlist (``files_to_modify`` union any explicit
    ``task.allowed_paths``)."""
    return touched_paths(source_workspace, ws) - set(allowed)
