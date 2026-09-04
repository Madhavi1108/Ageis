"""The walking-skeleton pipeline: one synchronous, headless run from a
requirement to a Trust Report. See docs/AEGIS_IMPLEMENTATION_PLAN.md Section
9 (Phase 1) and Section 7 (the connectedness invariant this mirrors at
reduced scale) -- each stage consumes the previous stage's typed output.

No job queue, no worker, no state machine: this is intentionally a single
function running the pipeline top to bottom, exactly as the walking skeleton
is meant to be (Section 7.2, "the narrowest possible end-to-end vertical
slice").
"""
from __future__ import annotations

from pathlib import Path

from aegis.agents.planning import propose_plan, validate_plan
from aegis.ai.provider import AIProvider
from aegis.ai.schema_guard import AIOutputInvalid
from aegis.analysis.mapping import rank_files
from aegis.analysis.python_ast import analyze
from aegis.artifacts import record_run
from aegis.debugging.repair_loop import run_repair_loop
from aegis.implementation.editor import EditorError, apply_edit_ops
from aegis.implementation.patcher import unified_diff
from aegis.repository.ingest import ingest_local
from aegis.repository.workspace import clone_rw
from aegis.sandbox.runner import SandboxRunner
from aegis.schemas.implementation import ImplementationResult
from aegis.schemas.trust_report import TrustReportV0
from aegis.verification.agent import verify
from aegis.verification.trust import build_trust_report


def _task_title(task_text: str) -> str:
    for line in task_text.splitlines():
        stripped = line.strip().lstrip("#").strip()
        if stripped:
            return stripped[:120]
    return "untitled task"


def run_pipeline(
    *,
    repo_path: str | Path,
    task_path: str | Path,
    provider: AIProvider,
    sandbox: SandboxRunner,
    record_artifact: bool = True,
) -> TrustReportV0:
    repo_path = str(repo_path)
    task_text = Path(task_path).read_text(encoding="utf-8")
    task_title = _task_title(task_text)
    task_key = Path(repo_path).resolve().name

    # 1. Ingest (reduced Phase 3) + 2. Analyze (reduced Phase 4)
    snapshot = ingest_local(repo_path)
    analysis = analyze(snapshot)

    # 3. Map (reduced Phase 7)
    candidates = rank_files(task_text, snapshot, analysis)
    candidate_paths = [c.path for c in candidates]
    target_file = candidate_paths[0] if candidate_paths else None
    target_file_head = ""
    if target_file:
        target_head_line = snapshot.file_by_path(target_file).abs_path.read_text(  # type: ignore[union-attr]
            encoding="utf-8"
        ).splitlines(keepends=True)
        target_file_head = target_head_line[0] if target_head_line else ""

    def _report(outcome: str, *, diff_text: str = "", **kwargs: object) -> TrustReportV0:
        report = build_trust_report(
            task_repo=repo_path,
            task_title=task_title,
            outcome=outcome,
            candidates=candidates,
            diff_text=diff_text,
            **kwargs,
        )
        if record_artifact:
            record_run(repo=repo_path, trust_report=report)
        return report

    # 4. Plan (reduced Phase 9, single call) + validate
    try:
        plan = propose_plan(
            task_key=task_key, task_text=task_text, candidate_files=candidate_paths, provider=provider
        )
    except AIOutputInvalid as exc:
        return _report("NOT_VERIFIED", limitations=[f"planning failed schema validation: {exc}"])

    validation = validate_plan(plan, snapshot)
    if validation.verdict != "APPROVED":
        return _report(
            "NOT_VERIFIED",
            plan=plan,
            limitations=[f"plan not approved ({validation.verdict}): {'; '.join(validation.reasons)}"],
        )

    # 5. Implement (reduced Phase 10) on a copy-on-write workspace
    ws = clone_rw(snapshot)
    try:
        impl_variables = {
            "task_key": task_key,
            "target_file": plan.files_to_modify[0] if plan.files_to_modify else target_file,
            "target_file_head": target_file_head,
            "plan_step_id": plan.steps[0].id if plan.steps else "s1",
        }
        try:
            impl = provider.complete(
                template="implementation", variables=impl_variables, schema=ImplementationResult
            )
            assert isinstance(impl, ImplementationResult)
        except AIOutputInvalid as exc:
            return _report(
                "NOT_VERIFIED", plan=plan, limitations=[f"implementation failed schema validation: {exc}"]
            )

        all_ops = []
        try:
            apply_edit_ops(ws, impl.edit_ops)
            all_ops.extend(impl.edit_ops)
        except EditorError as exc:
            return _report(
                "NOT_VERIFIED",
                plan=plan,
                diff_text=unified_diff(snapshot, ws),
                limitations=[f"editor error: {exc}"],
            )

        # 6. Test in the sandbox (reduced Phase 12) -- full suite, no selection
        test_command = sorted(f.path for f in snapshot.files if f.is_test)
        if not test_command:
            return _report(
                "NOT_VERIFIED", plan=plan, limitations=["repository has no test files to run"]
            )

        exec_result = sandbox.run_tests(ws, test_command)

        if exec_result.outcome == "PARTIALLY_SUPPORTED":
            return _report(
                "PARTIALLY_SUPPORTED",
                plan=plan,
                exec_result=exec_result,
                diff_text=unified_diff(snapshot, ws),
                limitations=[exec_result.reason or "sandbox unavailable"],
            )

        # 7. Bounded repair loop (reduced Phase 14)
        repair_result = None
        if exec_result.outcome != "PASS":
            repair_result = run_repair_loop(
                ws=ws,
                provider=provider,
                sandbox=sandbox,
                test_command=test_command,
                initial_exec_result=exec_result,
                task_key=task_key,
                target_file=impl_variables["target_file"],
                target_file_head=target_file_head,
                plan_step_id=impl_variables["plan_step_id"],
            )
            exec_result = repair_result.final_exec_result
            all_ops.extend(repair_result.applied_ops)

        # 8. Verify (reduced Phase 18: three mandatory criteria)
        verification = verify(
            plan=plan, snapshot=snapshot, ws=ws, exec_result=exec_result, all_edit_ops=all_ops
        )

        outcome = verification.verdict  # "VERIFIED" | "NOT_VERIFIED"
        limitations: list[str] = []
        if outcome != "VERIFIED":
            failing = [c.name for c in verification.criteria if c.verdict == "FAIL"]
            limitations.append(f"failed criteria: {failing}")
            if repair_result is not None and len(repair_result.attempts) >= 2:
                limitations.append("repair loop exhausted its 2-attempt budget without success")
                outcome = "SAFE_STOP"

        return _report(
            outcome,
            plan=plan,
            exec_result=exec_result,
            verification=verification,
            repair_attempts=repair_result.attempts if repair_result else [],
            limitations=limitations,
            diff_text=unified_diff(snapshot, ws),
        )
    finally:
        ws.cleanup()
