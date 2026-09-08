"""Guarded, side-effect-free projections of a task's persisted stage rows.

Every ``get_or_*`` service computes-on-miss; each helper here checks the stage's
repository row first and only calls the service when a row exists (guaranteeing
its pure-projection branch). A missing stage returns ``None``. Shared by
report_builder and metrics_workbook.
"""

from __future__ import annotations

from app.core.config import Settings
from app.core.errors import AppError
from app.repository.code_mappings import CodeMappingRepository
from app.repository.engineering_plans import EngineeringPlanRepository
from app.repository.failures import InvestigationRepository
from app.repository.impact_analyses import ImpactAnalysisRepository
from app.repository.implementations import ImplementationRepository
from app.repository.regression_plans import RegressionPlanRepository
from app.repository.repair_attempts import RepairAttemptRepository
from app.repository.reviews import ReviewRepository
from app.repository.scoring import RiskAssessmentRepository
from app.repository.test_cases import TestCaseRepository
from app.repository.verifications import VerificationRepository
from app.schemas.execution import TestExecution
from app.schemas.failure import FailureAnalysis
from app.schemas.impact import ImpactAnalysis
from app.schemas.implementation import ImplementationResult
from app.schemas.mapping import IssueCodeMapping
from app.schemas.plan import EngineeringPlan
from app.schemas.regression import RegressionResult
from app.schemas.repair import RepairResult
from app.schemas.review import ReviewReport
from app.schemas.scoring import PatchConfidence, PatchRiskAssessment
from app.schemas.testing import TestGeneration
from app.schemas.verification import VerificationResult
from sqlalchemy.orm import Session

from app.services import impact as impact_service
from app.services import implementation as implementation_service
from app.services import investigation as investigation_service
from app.services import mapping as mapping_service
from app.services import planning as planning_service
from app.services import regression as regression_service
from app.services import repair as repair_service
from app.services import review as review_service
from app.services import scoring as scoring_service
from app.services import testing as testing_service
from app.services import verification as verification_service


def _guard(fn):
    try:
        return fn()
    except AppError:
        return None
    except Exception:  # noqa: BLE001 -- a degraded stage is simply absent
        return None


def mapping(db: Session, task_id: str) -> IssueCodeMapping | None:
    if CodeMappingRepository(db).get_by_task(task_id) is None:
        return None
    return _guard(lambda: mapping_service.get_mapping(db, task_id))


def impact(db: Session, settings: Settings, task_id: str) -> ImpactAnalysis | None:
    if ImpactAnalysisRepository(db).get_by_task(task_id) is None:
        return None
    return _guard(
        lambda: impact_service.get_or_compute_impact(
            db, settings=settings, task_id=task_id
        )
    )


def plan(db: Session, task_id: str) -> EngineeringPlan | None:
    if EngineeringPlanRepository(db).get_latest_by_task(task_id) is None:
        return None
    return _guard(lambda: planning_service.get_plan(db, task_id))


def implementation(db: Session, task_id: str) -> ImplementationResult | None:
    if ImplementationRepository(db).get_latest_by_task(task_id) is None:
        return None
    return _guard(lambda: implementation_service.get_implementation(db, task_id))


def tests(db: Session, task_id: str) -> TestGeneration | None:
    if not TestCaseRepository(db).list_latest_by_task(task_id):
        return None
    return _guard(lambda: testing_service.get_tests(db, task_id))


def executions(db: Session, task_id: str) -> list[TestExecution]:
    return _guard(lambda: execution_service_list(db, task_id)) or []


def execution_service_list(db: Session, task_id: str) -> list[TestExecution]:
    from app.services import execution as execution_service

    return execution_service.list_executions(db, task_id)


def failures(db: Session, settings: Settings, task_id: str) -> FailureAnalysis | None:
    if InvestigationRepository(db).get_latest_by_task(task_id) is None:
        return None
    return _guard(
        lambda: investigation_service.get_or_investigate(
            db, settings=settings, task_id=task_id
        )
    )


def repairs(db: Session, settings: Settings, task_id: str) -> RepairResult | None:
    if not RepairAttemptRepository(db).list_for_task(task_id):
        return None
    return _guard(
        lambda: repair_service.get_or_repair(db, settings=settings, task_id=task_id)
    )


def regression(
    db: Session, settings: Settings, task_id: str
) -> RegressionResult | None:
    if RegressionPlanRepository(db).get_by_task(task_id) is None:
        return None
    return _guard(
        lambda: regression_service.get_or_plan(db, settings=settings, task_id=task_id)
    )


def review(db: Session, settings: Settings, task_id: str) -> ReviewReport | None:
    if ReviewRepository(db).get_by_task(task_id) is None:
        return None
    return _guard(
        lambda: review_service.get_or_review(db, settings=settings, task_id=task_id)
    )


def scores(
    db: Session, settings: Settings, task_id: str
) -> tuple[PatchConfidence, PatchRiskAssessment] | None:
    if RiskAssessmentRepository(db).get_by_task(task_id) is None:
        return None
    return _guard(
        lambda: scoring_service.get_or_score(db, settings=settings, task_id=task_id)
    )


def verification(
    db: Session, settings: Settings, task_id: str
) -> VerificationResult | None:
    if VerificationRepository(db).get_by_task(task_id) is None:
        return None
    return _guard(
        lambda: verification_service.get_or_verify(
            db, settings=settings, task_id=task_id
        )
    )
