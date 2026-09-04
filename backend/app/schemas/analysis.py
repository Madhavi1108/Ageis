"""API schemas for repository analysis. See docs/AEGIS_IMPLEMENTATION_PLAN.md Section 12.

RepositoryAnalysisResult carries confidence/evidence/error for consistency with the 18 AI
output schemas' shape (docs/AI_AGENT_DESIGN.md) even though this phase has zero AI/LLM
calls -- the Repository Analyst agent is deterministic AST analysis. confidence/evidence
are populated with deterministic values (evidence citing the config file consulted),
never model-derived.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from aegis.schemas.common import AgentError, Confidence, Evidence


class EntryPointRef(BaseModel):
    type: Literal["main_guard", "console_script", "asgi_app", "cli"]
    file: str | None
    symbol: str | None = None
    detail: str | None = None


class AnalyzeRequest(BaseModel):
    force: bool = Field(
        default=False, description="Re-run analysis even if a result already exists"
    )


class RepositoryAnalysisResult(BaseModel):
    snapshot_id: str
    entry_points: list[EntryPointRef]
    test_framework: str | None
    test_command: str | None
    package_manager: str | None
    build_backend: str | None
    symbol_count: int
    dependency_count: int
    unknowns: list[str]
    analysed_at: datetime
    duration_ms: int
    confidence: Confidence
    evidence: list[Evidence]
    error: AgentError | None = None
    job_id: str
