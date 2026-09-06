"""EditOp / EditOpsAI schema validation (docs/AEGIS_IMPLEMENTATION_PLAN.md
Section 18)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.implementation import EditOp, EditOpsAI


def test_edit_op_minimal_valid():
    op = EditOp(
        path="a.py",
        op="create",
        new="x = 1\n",
        plan_step_id="s1",
        rationale="add a.py",
    )
    assert op.anchor is None
    assert op.evidence == []


def test_edit_op_rejects_unknown_op_kind():
    with pytest.raises(ValidationError):
        EditOp(
            path="a.py",
            op="overwrite",
            new="x = 1\n",
            plan_step_id="s1",
            rationale="r",
        )


def test_edit_ops_ai_requires_at_least_one_op():
    with pytest.raises(ValidationError):
        EditOpsAI(edit_ops=[])


def test_edit_ops_ai_valid():
    result = EditOpsAI(
        edit_ops=[
            {
                "path": "a.py",
                "op": "replace",
                "anchor": "x = 1",
                "new": "x = 2",
                "plan_step_id": "s1",
                "rationale": "r",
                "evidence": [{"kind": "symbol", "ref": "a.py::x", "detail": "target"}],
            }
        ]
    )
    assert len(result.edit_ops) == 1
    assert result.edit_ops[0].evidence[0].kind == "symbol"
