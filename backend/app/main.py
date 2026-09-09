"""FastAPI app factory. See docs/AEGIS_IMPLEMENTATION_PLAN.md Section 10.

Run locally with: ``uvicorn app.main:app --reload`` (from backend/).
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.ratelimit import RateLimiter

from app.api import (
    analysis,
    executions,
    github,
    health,
    jobs,
    mapping,
    memory,
    reports,
    repositories,
    tasks,
)
from app.core.config import get_settings
from app.core.errors import (
    AppError,
    app_error_handler,
    http_exception_handler,
    validation_error_handler,
)
from app.core.logging import configure_logging, correlation_id_var


def _err(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"code": code, "message": message, "details": None, "evidence": None},
    )


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

    _max_body = settings.request_max_body_bytes
    _BODY_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

    @app.middleware("http")
    async def _limit_body_size(  # noqa: ANN001, ANN202
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        cl = request.headers.get("content-length")
        te = request.headers.get("transfer-encoding", "").lower()
        if cl is not None and cl.isdigit() and int(cl) > _max_body:
            return _err(
                413, "REQUEST_TOO_LARGE", f"request body exceeds {_max_body} bytes"
            )
        # A body-bearing request with no usable Content-Length (chunked / streamed)
        # can't be size-checked up front -- AEGIS has no streaming upload route,
        # so require a declared length rather than accept an unbounded body.
        if request.method in _BODY_METHODS and (cl is None or not cl.isdigit()):
            if "chunked" in te or te:
                return _err(
                    411, "LENGTH_REQUIRED", "a Content-Length header is required"
                )
        return await call_next(request)

    _rl = RateLimiter(
        per_minute=settings.rate_limit_per_minute, burst=settings.rate_limit_burst
    )

    @app.middleware("http")
    async def _rate_limit(  # noqa: ANN001, ANN202
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if not settings.rate_limit_enabled or request.url.path in (
            "/",
            "/healthz",
            "/readyz",
            "/metrics",
            "/version",
        ):
            return await call_next(request)
        key = request.headers.get("x-api-key")
        if not key:
            auth = request.headers.get("authorization", "")
            key = auth[7:].strip() if auth.lower().startswith("bearer ") else None
        key = key or (request.client.host if request.client else "unknown")
        allowed, retry_after = _rl.check(key)
        if not allowed:
            resp = _err(429, "RATE_LIMITED", "too many requests")
            resp.headers["Retry-After"] = str(retry_after)
            return resp
        return await call_next(request)

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
    app.include_router(executions.router)
    app.include_router(github.router)
    app.include_router(memory.router)
    app.include_router(jobs.router)
    app.include_router(reports.router)

    return app


app = create_app()
