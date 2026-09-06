"""Schema guard: one repair round, then clean failure."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from app.ai.schema_guard import AIOutputInvalid, validate_with_repair


class Toy(BaseModel):
    n: int
    kind: str


def test_valid_passes_through():
    out = validate_with_repair({"n": 1, "kind": "a"}, Toy)
    assert out.n == 1 and out.kind == "a"


def test_missing_field_no_repair_raises():
    with pytest.raises(AIOutputInvalid):
        validate_with_repair({"n": 1}, Toy)


def test_wrong_type_no_repair_raises():
    with pytest.raises(AIOutputInvalid):
        validate_with_repair({"n": "not-int", "kind": "a"}, Toy)


def test_repair_fn_called_once_and_fixes():
    calls = []

    def repair(raw, err):
        calls.append(err)
        return {**raw, "kind": "b"}

    out = validate_with_repair({"n": 2}, Toy, repair_fn=repair)
    assert out.kind == "b"
    assert len(calls) == 1


def test_repair_that_still_fails_raises_after_one_round():
    def repair(raw, err):
        return raw  # unchanged -> still invalid

    with pytest.raises(AIOutputInvalid) as ei:
        validate_with_repair({"n": 2}, Toy, repair_fn=repair)
    assert "after one repair round" in str(ei.value)
