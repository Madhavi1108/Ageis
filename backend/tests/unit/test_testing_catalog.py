"""Phase 11 catalog: static validity check + de-duplication
(docs/AEGIS_IMPLEMENTATION_PLAN.md Section 19)."""

from __future__ import annotations

from app.schemas.testing import TestCaseAI
from app.testing.catalog import check_syntax, deduplicate, existing_test_names


def test_check_syntax_valid():
    assert check_syntax("def test_x():\n    assert 1 == 1\n") is None


def test_check_syntax_invalid():
    error = check_syntax("def test_x(:\n    pass\n")
    assert error is not None
    assert "SyntaxError" in error


def test_existing_test_names_collects_top_level_test_functions():
    sources = {
        "test_a.py": "def test_one():\n    pass\n\ndef helper():\n    pass\n",
        "test_b.py": "def test_two():\n    pass\n",
    }
    assert existing_test_names(sources) == {"test_one", "test_two"}


def test_existing_test_names_ignores_unparsable_source():
    sources = {"test_a.py": "def test_one(:\n"}
    assert existing_test_names(sources) == set()


def _case(name="test_x", path="test_x.py"):
    return TestCaseAI(
        name=name,
        path=path,
        target_symbol="mod::fn",
        kind="BOUNDARY",
        rationale="r",
        code="def test_x():\n    pass\n",
    )


def test_deduplicate_drops_name_collision_with_existing():
    kept, dropped = deduplicate(
        [_case()], existing_names={"test_x"}, existing_paths=set()
    )
    assert kept == []
    assert dropped == [_case()]


def test_deduplicate_drops_path_collision_with_existing():
    kept, dropped = deduplicate(
        [_case()], existing_names=set(), existing_paths={"test_x.py"}
    )
    assert kept == []
    assert len(dropped) == 1


def test_deduplicate_drops_intra_batch_collision():
    a = _case(name="test_x", path="test_x.py")
    b = _case(name="test_x", path="test_other.py")
    kept, dropped = deduplicate([a, b], existing_names=set(), existing_paths=set())
    assert kept == [a]
    assert dropped == [b]


def test_deduplicate_keeps_non_colliding_case():
    kept, dropped = deduplicate(
        [_case()], existing_names={"test_unrelated"}, existing_paths={"other.py"}
    )
    assert kept == [_case()]
    assert dropped == []
