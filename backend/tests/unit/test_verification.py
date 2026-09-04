from aegis.implementation.editor import apply_edit_op
from aegis.repository.ingest import ingest_local
from aegis.repository.workspace import clone_rw
from aegis.schemas.implementation import EditOp
from aegis.schemas.plan import EngineeringPlan
from aegis.schemas.testing import TestExecutionResult, TestOutcome
from aegis.verification.agent import verify


def _plan(files_to_modify):
    return EngineeringPlan(
        problem_interpretation="p",
        files_to_modify=files_to_modify,
        steps=[{"id": "s1", "description": "d", "test_intent": "t"}],
        expected_behavior="e",
        rollback_strategy="r",
        source="AI",
        confidence={"value": 0.9, "basis": "FACT"},
    )


def _repo(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    return ingest_local(tmp_path)


def test_all_three_criteria_pass_yields_verified(tmp_path):
    snapshot = _repo(tmp_path)
    ws = clone_rw(snapshot)
    try:
        op = EditOp(path="a.py", op="replace", anchor="x = 1", new="x = 2", plan_step_id="s1", rationale="r")
        apply_edit_op(ws, op)
        exec_result = TestExecutionResult(
            command="pytest", exit_code=0, outcome="PASS",
            results=[TestOutcome(test_id="t::test_a", outcome="PASS")],
        )
        result = verify(
            plan=_plan(["a.py"]), snapshot=snapshot, ws=ws, exec_result=exec_result, all_edit_ops=[op]
        )
        assert result.verdict == "VERIFIED"
        assert result.all_pass()
    finally:
        ws.cleanup()


def test_failing_tests_yields_not_verified(tmp_path):
    snapshot = _repo(tmp_path)
    ws = clone_rw(snapshot)
    try:
        op = EditOp(path="a.py", op="replace", anchor="x = 1", new="x = 2", plan_step_id="s1", rationale="r")
        apply_edit_op(ws, op)
        exec_result = TestExecutionResult(
            command="pytest", exit_code=1, outcome="FAIL",
            results=[TestOutcome(test_id="t::test_a", outcome="FAIL")],
        )
        result = verify(
            plan=_plan(["a.py"]), snapshot=snapshot, ws=ws, exec_result=exec_result, all_edit_ops=[op]
        )
        assert result.verdict == "NOT_VERIFIED"
        names = {c.name: c.verdict for c in result.criteria}
        assert names["issue_tests_pass"] == "FAIL"
        assert names["no_unplanned_files"] == "PASS"
        assert names["patch_reapplies"] == "PASS"
    finally:
        ws.cleanup()


def test_unplanned_file_touched_yields_not_verified(tmp_path):
    snapshot = _repo(tmp_path)
    (tmp_path / "b.py").write_text("y = 1\n", encoding="utf-8")
    snapshot = ingest_local(tmp_path)
    ws = clone_rw(snapshot)
    try:
        op_a = EditOp(path="a.py", op="replace", anchor="x = 1", new="x = 2", plan_step_id="s1", rationale="r")
        op_b = EditOp(path="b.py", op="replace", anchor="y = 1", new="y = 2", plan_step_id="s1", rationale="r")
        apply_edit_op(ws, op_a)
        apply_edit_op(ws, op_b)  # out of scope: plan only allows a.py
        exec_result = TestExecutionResult(command="pytest", exit_code=0, outcome="PASS", results=[])
        result = verify(
            plan=_plan(["a.py"]), snapshot=snapshot, ws=ws, exec_result=exec_result,
            all_edit_ops=[op_a, op_b],
        )
        assert result.verdict == "NOT_VERIFIED"
        names = {c.name: c.verdict for c in result.criteria}
        assert names["no_unplanned_files"] == "FAIL"
    finally:
        ws.cleanup()


def test_unreproducible_change_fails_patch_reapplies(tmp_path):
    snapshot = _repo(tmp_path)
    ws = clone_rw(snapshot)
    try:
        # Mutate the workspace directly, without a corresponding recorded op.
        (ws.root / "a.py").write_text("x = 999\n", encoding="utf-8")
        fake_op = EditOp(path="a.py", op="replace", anchor="x = 1", new="x = 2", plan_step_id="s1", rationale="r")
        exec_result = TestExecutionResult(command="pytest", exit_code=0, outcome="PASS", results=[])
        result = verify(
            plan=_plan(["a.py"]), snapshot=snapshot, ws=ws, exec_result=exec_result, all_edit_ops=[fake_op]
        )
        assert result.verdict == "NOT_VERIFIED"
        names = {c.name: c.verdict for c in result.criteria}
        assert names["patch_reapplies"] == "FAIL"
    finally:
        ws.cleanup()
