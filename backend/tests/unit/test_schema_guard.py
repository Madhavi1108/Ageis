import pytest
from pydantic import BaseModel

from aegis.ai.schema_guard import AIOutputInvalid, validate_with_repair


class _Small(BaseModel):
    name: str
    count: int


def test_valid_raw_passes_immediately():
    result = _Small.model_validate({"name": "x", "count": 1})
    assert validate_with_repair({"name": "x", "count": 1}, _Small) == result


def test_invalid_raw_without_repair_fn_raises():
    with pytest.raises(AIOutputInvalid):
        validate_with_repair(
            {"name": "x", "count": "not-a-number"}, _Small, repair_fn=None
        )


def test_invalid_raw_repaired_successfully():
    calls = []

    def repair_fn(raw, error):
        calls.append((raw, error))
        return {**raw, "count": 7}

    result = validate_with_repair(
        {"name": "x", "count": "bad"}, _Small, repair_fn=repair_fn
    )
    assert result.count == 7
    assert len(calls) == 1


def test_invalid_raw_repair_also_fails_raises_and_stops_at_one_round():
    calls = []

    def repair_fn(raw, error):
        calls.append(1)
        return {**raw, "count": "still-bad"}

    with pytest.raises(AIOutputInvalid):
        validate_with_repair({"name": "x", "count": "bad"}, _Small, repair_fn=repair_fn)
    assert len(calls) == 1  # exactly one repair round, never more
