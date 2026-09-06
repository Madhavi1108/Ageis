"""AppError subclasses for the scoring layer. Same shape as
app/review/errors.py -- each carries its own status_code, so the existing
handler in app/main.py needs no new wiring.
"""

from __future__ import annotations

from fastapi import status

from app.core.errors import AppError


class ScoringTaskNotFoundError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(
            "SCORING_TASK_NOT_FOUND", message, status_code=status.HTTP_404_NOT_FOUND
        )


class ScoringImplementationMissingError(AppError):
    """PCS/CRS score the patch produced by Phase 10 -- there's nothing to
    score otherwise."""

    def __init__(self, message: str) -> None:
        super().__init__(
            "SCORING_IMPLEMENTATION_MISSING",
            message,
            status_code=status.HTTP_409_CONFLICT,
        )


class ScoringImpactMissingError(AppError):
    """The Change Risk Score is largely derived from the Phase 8 impact
    analysis (blast radius, centrality, public-API); it must exist first
    (GET /tasks/{id}/impact)."""

    def __init__(self, message: str) -> None:
        super().__init__(
            "SCORING_IMPACT_MISSING", message, status_code=status.HTTP_409_CONFLICT
        )


class ScoringRepositoryNotFoundError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(
            "SCORING_REPOSITORY_NOT_FOUND",
            message,
            status_code=status.HTTP_404_NOT_FOUND,
        )


class ScoringAnalysisMissingError(AppError):
    """The Repository Health Profile is computed from a repository's analysed
    snapshot (symbols, graph, files); analyse one first
    (POST /repositories/{id}/snapshots/{sid}/analysis)."""

    def __init__(self, message: str) -> None:
        super().__init__(
            "SCORING_ANALYSIS_MISSING", message, status_code=status.HTTP_409_CONFLICT
        )
