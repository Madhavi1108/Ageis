"""Phase 18 unit: the plan-alignment breakdown
(docs/AEGIS_IMPLEMENTATION_PLAN.md Section 26, step 2).
"""

from __future__ import annotations

from app.verification.alignment import plan_alignment
from tests.unit.test_verification_criteria import _inp


def test_alignment_clean():
    a = plan_alignment(_inp())
    assert a.steps_total == 1
    assert a.steps_implemented == 1
    assert a.unimplemented_steps == []
    assert a.unplanned_files == []
    assert a.files_touched == ["invoice.py"]


def test_alignment_reports_unimplemented_step():
    a = plan_alignment(
        _inp(plan_steps=[{"id": "s1"}, {"id": "s2"}], traceability={"s1": ["invoice.py"]})
    )
    assert a.steps_total == 2
    assert a.steps_implemented == 1
    assert a.unimplemented_steps == ["s2"]


def test_alignment_reports_unplanned_file():
    a = plan_alignment(_inp(touched_files=["invoice.py", "z_extra.py"]))
    assert a.unplanned_files == ["z_extra.py"]
    assert a.files_touched == ["invoice.py", "z_extra.py"]


def test_alignment_empty_traceability_marks_all_steps_unimplemented():
    a = plan_alignment(_inp(traceability={}))
    assert a.steps_implemented == 0
    assert a.unimplemented_steps == ["s1"]
