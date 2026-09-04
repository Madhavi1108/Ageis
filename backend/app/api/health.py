"""Liveness and build-metadata endpoints. See docs/AEGIS_IMPLEMENTATION_PLAN.md Section 10."""

from __future__ import annotations

from fastapi import APIRouter

from app.version import get_version_info

router = APIRouter(tags=["health"])


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/version")
def version() -> dict[str, str | None]:
    return get_version_info()
