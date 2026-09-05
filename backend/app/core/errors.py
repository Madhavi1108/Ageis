"""Typed error envelope and FastAPI exception handlers.

See docs/AEGIS_IMPLEMENTATION_PLAN.md Section 10: typed error envelope
``{code, message, details, evidence?}``. Reuses ``aegis.schemas.common.Evidence``
so the vocabulary for "what backs this conclusion/error" stays aligned across
the Phase 1 pipeline and the Phase 2 API.
"""

from __future__ import annotations

from typing import Any

from fastapi import Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from aegis.schemas.common import Evidence


class ErrorEnvelope(BaseModel):
    """The typed shape every AEGIS API error response takes."""

    code: str
    message: str
    details: dict[str, Any] | None = None
    evidence: list[Evidence] | None = None


class AppError(Exception):
    """Raise to produce a typed ``ErrorEnvelope`` response with a given status code."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: dict[str, Any] | None = None,
        evidence: list[Evidence] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details
        self.evidence = evidence

    def to_envelope(self) -> ErrorEnvelope:
        return ErrorEnvelope(
            code=self.code,
            message=self.message,
            details=self.details,
            evidence=self.evidence,
        )


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code, content=exc.to_envelope().model_dump()
    )


async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    envelope = ErrorEnvelope(
        code="VALIDATION_ERROR",
        message="Request payload failed validation.",
        # jsonable_encoder: a model/root validator that raises ValueError puts the
        # exception object in `ctx`, which is not directly JSON serializable.
        details={"errors": jsonable_encoder(exc.errors())},
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=jsonable_encoder(envelope),
    )


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    envelope = ErrorEnvelope(
        code=f"HTTP_{exc.status_code}",
        message=str(exc.detail) if exc.detail else "Request failed.",
    )
    return JSONResponse(status_code=exc.status_code, content=envelope.model_dump())
