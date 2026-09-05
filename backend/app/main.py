"""FastAPI app factory. See docs/AEGIS_IMPLEMENTATION_PLAN.md Section 10.

Run locally with: ``uvicorn app.main:app --reload`` (from backend/).
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import analysis, health, mapping, repositories, tasks
from app.core.config import get_settings
from app.core.errors import (
    AppError,
    app_error_handler,
    http_exception_handler,
    validation_error_handler,
)
from app.core.logging import configure_logging, correlation_id_var


async def _correlation_id_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    correlation_id = request.headers.get("x-correlation-id") or str(uuid.uuid4())
    token = correlation_id_var.set(correlation_id)
    try:
        response = await call_next(request)
    finally:
        correlation_id_var.reset(token)
    response.headers["x-correlation-id"] = correlation_id
    return response


def create_app() -> FastAPI:
    # Fail fast: a malformed/missing required env var raises here, at process
    # start, rather than lazily on first request.
    settings = get_settings()
    configure_logging(settings)

    app = FastAPI(title="AEGIS API", version="0.2.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.middleware("http")(_correlation_id_middleware)

    # FastAPI's add_exception_handler is typed against the base Exception
    # signature; narrower per-exception-type handlers are the documented
    # pattern (https://fastapi.tiangolo.com/tutorial/handling-errors/) but
    # don't satisfy that signature exactly.
    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]

    app.include_router(health.router)
    app.include_router(repositories.router)
    app.include_router(analysis.router)
    app.include_router(mapping.router)
    app.include_router(tasks.router)

    return app


app = create_app()
