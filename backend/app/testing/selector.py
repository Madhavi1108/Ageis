"""Targeted-set selection (docs/AEGIS_IMPLEMENTATION_PLAN.md Section 19,
"Targeted-set selection for execution"). Phase 12 runs this set first before
any regression subset; today it is simply every non-``INVALID`` generated
case -- each one was synthesized specifically to exercise changed behaviour,
so all of them are "targeted" by construction."""

from __future__ import annotations

from app.schemas.testing import TestCase


def select_targeted_set(cases: list[TestCase]) -> list[str]:
    return [c.name for c in cases if c.status != "INVALID"]
