"""Per-stage model-tier routing (ADR-0019, docs/AI_AGENT_DESIGN.md Section 4).

A plain Python map rather than ``ai/routing.yaml`` (the ADR's wording): PyYAML
is not a declared dependency, and the ADR's actual requirement -- "tier per
stage is config, overridable per deployment" -- is met by this constant plus
the ``AEGIS_AI_TIER_<STAGE>`` environment override.

``cheap``  : high-volume, low reasoning depth.
``frontier``: correctness-critical reasoning (planning, edit-ops, RCA, review).
"""

from __future__ import annotations

import os
from typing import Literal

Tier = Literal["cheap", "frontier"]

STAGE_TIERS: dict[str, Tier] = {
    "task_normalization": "cheap",
    "task_type": "cheap",
    "mapping_rerank": "cheap",
    "test_triage": "cheap",
    "summarization": "cheap",
    "trace_phrasing": "cheap",
    "planning": "frontier",
    "implementation": "frontier",
    "test_synthesis": "frontier",
    "root_cause": "frontier",
    "code_review": "frontier",
}


def tier_for(stage: str) -> Tier:
    """The configured tier for ``stage``. An ``AEGIS_AI_TIER_<STAGE>`` env var
    (e.g. ``AEGIS_AI_TIER_PLANNING=cheap``) overrides the table for a
    deployment; an unknown stage defaults to ``frontier`` (safe side)."""
    override = os.environ.get(f"AEGIS_AI_TIER_{stage.upper()}")
    if override in ("cheap", "frontier"):
        return override  # type: ignore[return-value]
    return STAGE_TIERS.get(stage, "frontier")
