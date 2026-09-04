"""API schemas for repository ingestion. See docs/AEGIS_IMPLEMENTATION_PLAN.md Section 11."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class RepositoryRef(BaseModel):
    id: str
    source_type: Literal["LOCAL", "GITHUB"]
    url_or_path: str
    default_branch: str | None = None
    name: str
    owner: str | None = None
    created_at: datetime
    updated_at: datetime


class RepositoryCreateRequest(BaseModel):
    source_type: Literal["LOCAL", "GITHUB"]
    url_or_path: str
    name: str | None = Field(
        default=None, description="Derived from the URL/path if omitted"
    )
    owner: str | None = None
    default_branch: str | None = None


class IngestRequest(BaseModel):
    branch: str | None = None
    depth: int | None = None
    force: bool = Field(
        default=False,
        description="Refresh/rebuild an already-ingested commit's snapshot",
    )


class IngestResult(BaseModel):
    snapshot_id: str
    repository_id: str
    commit_sha: str
    branch: str | None
    status: Literal["INGESTING", "READY", "PARTIALLY_SUPPORTED", "FAILED"]
    limit_reason: str | None = None
    file_count: int
    total_bytes: int
    languages: dict[str, int]
    ingested_at: datetime | None
    job_id: str
