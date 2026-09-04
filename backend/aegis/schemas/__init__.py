"""Real Pydantic schemas from docs/AI_AGENT_DESIGN.md Sections 6-7.

These are the actual contracts the full system uses -- Phase 1 implements
reduced logic behind them, not reduced schemas. Later phases extend behavior
without changing these shapes.
"""

from aegis.schemas.common import AgentError, Confidence, Evidence
from aegis.schemas.implementation import EditOp, ImplementationResult
from aegis.schemas.plan import EngineeringPlan, PlanStep, PlanValidation
from aegis.schemas.testing import TestExecutionResult, TestOutcome
from aegis.schemas.trust_report import TrustReportV0
from aegis.schemas.verification import Criterion, VerificationResult

__all__ = [
    "AgentError",
    "Confidence",
    "Evidence",
    "EditOp",
    "ImplementationResult",
    "EngineeringPlan",
    "PlanStep",
    "PlanValidation",
    "TestExecutionResult",
    "TestOutcome",
    "TrustReportV0",
    "Criterion",
    "VerificationResult",
]
