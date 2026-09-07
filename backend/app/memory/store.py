"""Assemble a completed-task memory record from the persisted pipeline rows
(docs/AEGIS_IMPLEMENTATION_PLAN.md Section 28, ADR-0016).

``build_record`` mirrors ``verification._collect_inputs``: it only reads. The
service (``app/services/memory.py``) persists the result and recomputes the
per-repository aggregate.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.memory.signatures import failure_signatures, fix_summary
from app.repository.code_mappings import CodeMappingRepository
from app.repository.engineering_plans import EngineeringPlanRepository
from app.repository.failures import FailureRepository, InvestigationRepository
from app.repository.implementations import ImplementationRepository
from app.repository.issues import IssueRepository
from app.repository.patches import PatchRepository
from app.repository.repair_attempts import RepairAttemptRepository
from app.repository.reviews import ReviewFindingRepository, ReviewRepository
from app.repository.tasks import TaskRepository
from app.repository.verifications import VerificationRepository


def _issue_text(task, issue) -> str:
    if issue is not None and issue.body_sanitized:
        head = issue.title.strip() if issue.title else ""
        return f"{head}\n{issue.body_sanitized}".strip()
    return task.description_sanitized


def _touched_files(impl, patch) -> list[str]:
    out: set[str] = set()
    if patch is not None:
        out.update(patch.touched_paths or [])
    if impl is not None:
        for paths in (impl.traceability or {}).values():
            out.update(paths or [])
    return sorted(out)


def _touched_symbols(plan, mapping, failures, touched_files: list[str]) -> list[str]:
    out: set[str] = set()
    if plan is not None:
        out.update(plan.symbols_to_modify or [])
    touched = set(touched_files)
    for c in (mapping.candidates if mapping is not None else []) or []:
        if c.get("path") in touched:
            out.update(c.get("symbols") or [])
    for f in failures or []:
        for fr in getattr(f, "frames", None) or []:
            if isinstance(fr, dict) and fr.get("in_diff") and fr.get("symbol_id"):
                out.add(fr["symbol_id"])
    return sorted(out)


def _review_summary(review, findings) -> dict:
    if review is None:
        return {"reviewed": False}
    return {
        "reviewed": True,
        "blocking": bool(review.blocking),
        "counts": review.counts or {},
        "policy_gaps": list(review.policy_gaps or []),
        "open_high_critical": [
            f"{f.severity} {f.category} {f.file or '-'}"
            for f in findings
            if f.status == "OPEN" and f.severity in ("CRITICAL", "HIGH")
        ],
    }


def _plan_snapshot(plan) -> dict:
    if plan is None:
        return {}
    return {
        "version": plan.version,
        "problem_interpretation": plan.problem_interpretation,
        "expected_behavior": plan.expected_behavior,
        "files_to_modify": list(plan.files_to_modify or []),
        "symbols_to_modify": list(plan.symbols_to_modify or []),
        "steps": list(plan.steps or []),
        "rollback_strategy": plan.rollback_strategy,
        "validation_verdict": plan.validation_verdict,
    }


def _repair_summary(db: Session, task_id: str) -> dict | None:
    for row in RepairAttemptRepository(db).list_for_task(task_id):
        if row.run_summary:
            return row.run_summary
    return None


def build_record(db: Session, *, task_id: str, outcome: str) -> dict:
    task = TaskRepository(db).get(task_id)
    assert task is not None

    issue = (
        IssueRepository(db).get(task.issue_id) if task.issue_id else None
    )
    plan = EngineeringPlanRepository(db).get_latest_by_task(task_id)
    impl = ImplementationRepository(db).get_latest_by_task(task_id)
    patch = (
        PatchRepository(db).get_by_implementation(impl.id) if impl is not None else None
    )
    mapping = CodeMappingRepository(db).get_by_task(task_id)
    review = ReviewRepository(db).get_by_task(task_id)
    findings = ReviewFindingRepository(db).list_for_task(task_id)
    verification = VerificationRepository(db).get_by_task(task_id)

    investigation = InvestigationRepository(db).get_latest_by_task(task_id)
    failures = (
        FailureRepository(db).list_for_execution(investigation.execution_id)
        if investigation is not None
        else []
    )
    repair_summary = _repair_summary(db, task_id)

    touched_files = _touched_files(impl, patch)

    return {
        "repository_id": task.repository_id,
        "issue_text_sanitized": _issue_text(task, issue),
        "touched_symbols": _touched_symbols(plan, mapping, failures, touched_files),
        "touched_files": touched_files,
        "failure_signatures": failure_signatures(
            investigation, failures, repair_summary
        ),
        "fix_summary": fix_summary(plan, verification, repair_summary, outcome),
        "plan_ref": _plan_snapshot(plan),
        "patch_ref": patch.artifact_id if patch is not None else None,
        "review_summary": _review_summary(review, findings),
        "verification_verdict": (
            verification.verdict if verification is not None else None
        ),
        "outcome": outcome,
    }
