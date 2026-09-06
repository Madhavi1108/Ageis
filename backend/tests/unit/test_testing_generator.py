"""Phase 11 generator: case-matrix construction + workspace materialization."""

from __future__ import annotations

from app.implementation.workspace_rw import clone_rw
from app.schemas.testing import TestCaseAI
from app.testing.generator import build_case_matrix, write_into_workspace


def test_case_matrix_covers_all_kinds_per_symbol():
    matrix = build_case_matrix(["mod::fn"])
    kinds = {row["kind"] for row in matrix}
    assert kinds == {"EDGE", "NEGATIVE", "BOUNDARY", "REGRESSION", "ISSUE_SPECIFIC"}
    assert all(row["target_symbol"] == "mod::fn" for row in matrix)


def test_case_matrix_empty_for_no_symbols():
    assert build_case_matrix([]) == []


def test_write_into_workspace_creates_new_files(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "a.py").write_text("x = 1\n", encoding="utf-8")
    ws = clone_rw("snap-1", source)
    try:
        case = TestCaseAI(
            name="test_x",
            path="test_x.py",
            target_symbol="a::x",
            kind="BOUNDARY",
            rationale="r",
            code="def test_x():\n    assert True\n",
        )
        write_into_workspace(ws, [case])
        assert ws.path_for("test_x.py").read_text() == "def test_x():\n    assert True\n"
    finally:
        ws.cleanup()
