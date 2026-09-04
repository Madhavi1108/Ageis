"""Scope guard (reduced). See docs/AEGIS_IMPLEMENTATION_PLAN.md Section 11 /
Phase 9's scope tracker: compares touched files against the plan's declared
allowlist and flags anything outside it.
"""
from __future__ import annotations

from aegis.repository.ingest import Snapshot
from aegis.repository.workspace import RWWorkspace
from aegis.implementation.patcher import touched_paths


def unplanned_files(snapshot: Snapshot, ws: RWWorkspace, allowed: list[str]) -> set[str]:
    """Files touched in `ws` relative to `snapshot` that are not in the
    plan's `files_to_modify` allowlist."""
    return touched_paths(snapshot, ws) - set(allowed)
