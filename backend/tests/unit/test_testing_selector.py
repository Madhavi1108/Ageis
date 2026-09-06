"""Phase 11 selector: the targeted execution set is every non-INVALID case."""

from __future__ import annotations

from datetime import datetime, timezone

from app.schemas.testing import TestCase
from app.testing.selector import select_targeted_set


def _case(name, status):
    return TestCase(
        name=name,
        path=f"{name}.py",
        target_symbol="mod::fn",
        kind="BOUNDARY",
        rationale="r",
        code="def x(): pass",
        evidence=[],
        status=status,
        invalid_reason=None,
        created_at=datetime.now(timezone.utc),
    )


def test_selects_only_non_invalid():
    cases = [
        _case("test_a", "GENERATED"),
        _case("test_b", "INVALID"),
        _case("test_c", "GENERATED"),
    ]
    assert select_targeted_set(cases) == ["test_a", "test_c"]


def test_empty_when_all_invalid():
    assert select_targeted_set([_case("test_a", "INVALID")]) == []
