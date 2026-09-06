"""Per-stage selection policy."""

from __future__ import annotations

from app.testing.regression import Classified, select_for_stage

_CLASSIFIED = [
    Classified("a::t", "a", "TARGETED", "r", None, 0),
    Classified("b::t", "b", "RELATED", "r", None, 1),
    Classified("c::t", "c", "REGRESSION", "r", None, None),
    Classified("d::t", "d", "FULL", "r", None, None),
]


def test_repair_stage_is_targeted_plus_related():
    sel = select_for_stage(_CLASSIFIED, "repair", mode="smart")
    assert sel.test_ids == ["a::t", "b::t"]
    assert sel.justification is None


def test_preverify_full_mode_is_everything():
    sel = select_for_stage(_CLASSIFIED, "pre_verification", mode="full")
    assert sel.test_ids == ["a::t", "b::t", "c::t", "d::t"]


def test_preverify_smart_mode_omits_full_only_with_justification():
    sel = select_for_stage(_CLASSIFIED, "pre_verification", mode="smart")
    assert sel.test_ids == ["a::t", "b::t", "c::t"]
    assert sel.justification and "3 of 4" in sel.justification
    assert sel.risk_note and "mode=full" in sel.risk_note


def test_preverify_smart_no_omission_no_justification():
    only_covered = _CLASSIFIED[:3]
    sel = select_for_stage(only_covered, "pre_verification", mode="smart")
    assert sel.test_ids == ["a::t", "b::t", "c::t"]
    assert sel.justification is None
