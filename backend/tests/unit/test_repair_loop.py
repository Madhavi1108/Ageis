from aegis.debugging.repair_loop import MAX_REPAIR_ITERATIONS, run_repair_loop
from aegis.repository.ingest import ingest_local
from aegis.repository.workspace import clone_rw
from aegis.schemas.testing import TestExecutionResult, TestOutcome


class _AlwaysFailProvider:
    """Returns a schema-valid no-op-ish edit every time; never fixes anything."""

    name = "stub"
    calls = 0

    def complete(self, *, template, variables, schema, **kwargs):
        self.calls += 1
        return schema.model_validate(
            {
                "edit_ops": [
                    {
                        "path": variables["target_file"],
                        "op": "insert",
                        "anchor": variables["target_file_head"],
                        "new": f"# attempt {self.calls}\n",
                        "plan_step_id": variables["plan_step_id"],
                        "rationale": "stub",
                        "evidence": [],
                    }
                ]
            }
        )


class _AlwaysFailSandbox:
    def run_tests(self, ws, test_command):
        return TestExecutionResult(
            command="pytest",
            exit_code=1,
            outcome="FAIL",
            results=[TestOutcome(test_id="t::test_x", outcome="FAIL")],
        )


def _workspace(tmp_path):
    (tmp_path / "m.py").write_text("value = 1\n", encoding="utf-8")
    snapshot = ingest_local(tmp_path)
    return clone_rw(snapshot)


def test_repair_loop_never_exceeds_the_bound(tmp_path):
    ws = _workspace(tmp_path)
    try:
        initial = TestExecutionResult(
            command="pytest", exit_code=1, outcome="FAIL",
            results=[TestOutcome(test_id="t::test_x", outcome="FAIL")],
        )
        provider = _AlwaysFailProvider()
        result = run_repair_loop(
            ws=ws,
            provider=provider,
            sandbox=_AlwaysFailSandbox(),
            test_command=["m.py"],
            initial_exec_result=initial,
            task_key="k",
            target_file="m.py",
            target_file_head="value = 1\n",
            plan_step_id="s1",
        )
        assert len(result.attempts) == MAX_REPAIR_ITERATIONS == 2
        assert provider.calls == 2
        assert result.final_exec_result.outcome == "FAIL"
    finally:
        ws.cleanup()


class _EventuallyPassSandbox:
    def __init__(self):
        self.calls = 0

    def run_tests(self, ws, test_command):
        self.calls += 1
        if self.calls >= 1:  # the single repair attempt "fixes" it
            return TestExecutionResult(command="pytest", exit_code=0, outcome="PASS", results=[])
        return TestExecutionResult(command="pytest", exit_code=1, outcome="FAIL", results=[])


def test_repair_loop_stops_early_once_green(tmp_path):
    ws = _workspace(tmp_path)
    try:
        initial = TestExecutionResult(command="pytest", exit_code=1, outcome="FAIL", results=[])
        provider = _AlwaysFailProvider()
        sandbox = _EventuallyPassSandbox()
        result = run_repair_loop(
            ws=ws,
            provider=provider,
            sandbox=sandbox,
            test_command=["m.py"],
            initial_exec_result=initial,
            task_key="k",
            target_file="m.py",
            target_file_head="value = 1\n",
            plan_step_id="s1",
        )
        assert len(result.attempts) == 1  # stopped as soon as it went green
        assert result.attempts[0].outcome == "GREEN"
        assert result.final_exec_result.outcome == "PASS"
    finally:
        ws.cleanup()


def test_repair_loop_no_attempts_when_already_passing(tmp_path):
    ws = _workspace(tmp_path)
    try:
        initial = TestExecutionResult(command="pytest", exit_code=0, outcome="PASS", results=[])
        provider = _AlwaysFailProvider()
        result = run_repair_loop(
            ws=ws,
            provider=provider,
            sandbox=_AlwaysFailSandbox(),
            test_command=["m.py"],
            initial_exec_result=initial,
            task_key="k",
            target_file="m.py",
            target_file_head="value = 1\n",
            plan_step_id="s1",
        )
        assert result.attempts == []
        assert provider.calls == 0
    finally:
        ws.cleanup()
