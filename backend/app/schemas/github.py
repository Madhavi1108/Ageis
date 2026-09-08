"""GitHub provider + pull-request schemas
(docs/AEGIS_IMPLEMENTATION_PLAN.md Section 27, ADR-0015). Plain Pydantic v2.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas._base import StrictModel

PRMode = Literal["LOCAL_ARTIFACT", "GITHUB"]
PRState = Literal["DRAFTED", "CREATED", "FAILED"]


class GitHubRepoInfo(BaseModel):
    full_name: str
    default_branch: str
    private: bool
    html_url: str
    description: str | None = None


class GitHubIssueInfo(BaseModel):
    number: int
    title: str
    body: str
    state: str
    html_url: str


class IssueRef(BaseModel):
    """The persisted Issue row after a GitHub import."""

    id: str
    repository_id: str
    source: str
    external_ref: str | None = None
    title: str
    imported_at: datetime


class PullRequestCreateRequest(StrictModel):
    approved: bool = Field(
        default=False,
        description="human approval for a protected-branch / external PR write",
    )


class PullRequestDraft(BaseModel):
    """The assembled PR before any GitHub call -- what a LOCAL_ARTIFACT row carries."""

    task_id: str
    title: str
    body: str
    base: str
    head: str
    mode: PRMode


class PullRequestOut(BaseModel):
    id: str
    task_id: str
    mode: PRMode
    title: str
    body_artifact_id: str
    branch: str | None = None
    commit_sha: str | None = None
    github_url: str | None = None
    github_number: int | None = None
    state: PRState
    failure_reason: str | None = None
    created_at: datetime
