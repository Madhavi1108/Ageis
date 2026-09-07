"""Acceptance (docs/AEGIS_IMPLEMENTATION_PLAN.md Section 27): a PR is produced
only for a VERIFIED task; without credentials only a local PR-body artifact is
written (every required section present); with a mocked token + approval a real
``201`` yields ``state=CREATED``; a mocked ``403`` yields ``state=FAILED`` and
never a false "created". Tokens never appear in the logs.
"""

from __future__ import annotations

from pathlib import Path

import httpx

from app.analysis.analyze import analyze_snapshot
from app.core.config import Settings
from app.core.security import contains_secret
from app.github.client import GitHubClient
from app.ingestion.ingest import ingest_repository
from app.repository.repositories import RepositoryRepository
from app.repository.snapshots import SnapshotRepository
from app.repository.tasks import TaskRepository
from app.repository.verifications import VerificationRepository
from app.schemas.implementation import EditOpsAI
from app.schemas.plan import EngineeringPlanAI
from app.schemas.repository import IngestRequest
from app.schemas.task import TaskCreate
from app.services import impact as impact_service
from app.services import implementation as implementation_service
from app.services import mapping as mapping_service
from app.services import planning as planning_service
from app.services import pr as pr_service
from app.services import tasks as tasks_service
from app.services import verification as verification_service

_TOKEN = "ghp_" + "q" * 36

_PLAN = EngineeringPlanAI.model_validate(
    {
        "problem_interpretation": "cap discount at 0.5",
        "assumptions": [],
        "files_to_inspect": ["invoice.py"],
        "files_to_modify": ["invoice.py"],
        "symbols_to_modify": ["invoice.py::calculate_total"],
        "dependencies": [],
        "steps": [
            {"id": "s1", "description": "clamp", "test_intent": "90==50", "evidence_refs": []}
        ],
        "test_strategy": {"approach": "boundary"},
        "expected_behavior": "the discount is capped at 0.5",
        "regression_risks": [],
        "rollback_strategy": "revert invoice.py",
        "source": "AI",
        "confidence": {"value": 0.8, "basis": "INFERENCE"},
        "evidence": [],
    }
)
_EDIT = EditOpsAI.model_validate(
    {
        "edit_ops": [
            {
                "path": "invoice.py",
                "op": "replace",
                "anchor": "return price * (1 - discount)",
                "new": "discount = min(discount, 0.5)\n    return price * (1 - discount)",
                "plan_step_id": "s1",
                "rationale": "cap",
                "evidence": [],
            }
        ]
    }
)


class _Provider:
    name = "fake"

    def complete(self, *, template, schema, **_kw):
        if template == "planning":
            return _PLAN
        if template == "implementation":
            return _EDIT
        if template == "code_review":
            return schema.model_validate({"findings": []})
        raise AssertionError(template)


def _verified_task(db_session, ingestion_settings, fixture) -> str:
    repo = RepositoryRepository(db_session).get_or_create(
        source_type="LOCAL", url_or_path=str(fixture), name="acc"
    )
    res = ingest_repository(
        db_session, repository=repo, request=IngestRequest(), settings=ingestion_settings
    )
    snap = SnapshotRepository(db_session).get(res.snapshot_id)
    analyze_snapshot(db_session, snapshot=snap, settings=ingestion_settings)
    task_md = (fixture / "task.md").read_text(encoding="utf-8")
    task_id = tasks_service.create_task(
        db_session,
        settings=ingestion_settings,
        payload=TaskCreate(repository_id=repo.id, text=task_md),
    ).task.id
    p = _Provider()
    mapping_service.run_mapping(db_session, settings=ingestion_settings, task_id=task_id)
    impact_service.get_or_compute_impact(
        db_session, settings=ingestion_settings, task_id=task_id
    )
    planning_service.generate_plan(
        db_session, settings=ingestion_settings, task_id=task_id, provider=p
    )
    planning_service.validate_plan_for_task(db_session, task_id)
    implementation_service.generate_implementation(
        db_session, settings=ingestion_settings, task_id=task_id, provider=p
    )
    verification_service.get_or_verify(
        db_session, settings=ingestion_settings, task_id=task_id, provider=p
    )
    # Docker-less -> PARTIAL; a human APPROVE lands it at VERIFIED
    verification_service.resolve_decision(
        db_session,
        settings=ingestion_settings,
        task_id=task_id,
        decision="APPROVE",
        reason="manually validated",
        actor="approver@x",
    )
    live = VerificationRepository(db_session).get_by_task(task_id)
    assert live.verdict == "VERIFIED"
    return task_id


def _mock_client(handler) -> GitHubClient:
    return GitHubClient(
        token=_TOKEN,
        base_url="https://api.github.test",
        transport=httpx.MockTransport(handler),
    )


def test_local_artifact_has_every_section(db_session, ingestion_settings, acceptance_fixture_path):
    task_id = _verified_task(db_session, ingestion_settings, acceptance_fixture_path)

    out = pr_service.create_pr(
        db_session,
        settings=ingestion_settings,  # no github_token
        task_id=task_id,
        github_client=_mock_client(lambda r: httpx.Response(500)),  # must not be called
        approved=True,
    )
    assert out.mode == "LOCAL_ARTIFACT"
    assert out.state == "DRAFTED"

    from app.repository.artifacts import ArtifactRepository

    art = ArtifactRepository(db_session).get(out.body_artifact_id)
    body = Path(art.uri).read_text(encoding="utf-8")
    for header in (
        "## Summary",
        "## Issue reference",
        "## Files changed",
        "## Tests added",
        "## Tests executed & results",
        "## Review results",
        "## Risk & confidence",
        "## Plan alignment",
        "## Verification",
        "## Known limitations",
    ):
        assert header in body, header
    assert "cap discount at 0.5" in body
    assert "Verdict: **VERIFIED**" in body


def test_github_pr_created_on_201(db_session, acceptance_fixture_path, tmp_path):
    settings = Settings(
        ingestion_local_roots=[str(acceptance_fixture_path.parent)],
        artifacts_root=str(tmp_path / "artifacts"),
        github_token=_TOKEN,
        _env_file=None,
    )
    ingestion_settings = settings
    task_id = _verified_task(db_session, ingestion_settings, acceptance_fixture_path)
    # point the task's repository at GitHub for the write path
    repo = RepositoryRepository(db_session).get(
        TaskRepository(db_session).get(task_id).repository_id
    )
    repo.source_type = "GITHUB"
    repo.url_or_path = "https://github.com/octo/demo"
    repo.default_branch = "main"
    db_session.commit()

    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(f"{request.method} {request.url.path}")
        if request.url.path.endswith("/git/ref/heads/main"):
            return httpx.Response(200, json={"object": {"sha": "basesha"}})
        if request.url.path.endswith("/git/refs"):
            return httpx.Response(201, json={})
        if "/contents/" in request.url.path:
            return httpx.Response(201, json={"commit": {"sha": "filesha"}})
        if request.url.path.endswith("/pulls"):
            return httpx.Response(
                201,
                json={"html_url": "https://github.com/octo/demo/pull/9", "number": 9},
            )
        return httpx.Response(404, json={"message": "?"})

    out = pr_service.create_pr(
        db_session,
        settings=settings,
        task_id=task_id,
        github_client=_mock_client(handler),
        approved=True,
    )
    assert out.mode == "GITHUB"
    assert out.state == "CREATED"
    assert out.github_url.endswith("/pull/9")
    assert out.github_number == 9
    assert out.commit_sha == "filesha"
    assert any("pulls" in c for c in calls)
    assert any("/contents/invoice.py" in c for c in calls)


def test_github_pr_failed_on_403_is_not_a_false_created(db_session, acceptance_fixture_path, tmp_path):
    settings = Settings(
        ingestion_local_roots=[str(acceptance_fixture_path.parent)],
        artifacts_root=str(tmp_path / "artifacts"),
        github_token=_TOKEN,
        _env_file=None,
    )
    task_id = _verified_task(db_session, settings, acceptance_fixture_path)
    repo = RepositoryRepository(db_session).get(
        TaskRepository(db_session).get(task_id).repository_id
    )
    repo.source_type = "GITHUB"
    repo.url_or_path = "https://github.com/octo/demo"
    repo.default_branch = "main"
    db_session.commit()

    out = pr_service.create_pr(
        db_session,
        settings=settings,
        task_id=task_id,
        github_client=_mock_client(
            lambda r: httpx.Response(403, json={"message": "no write access"})
        ),
        approved=True,
    )

    assert out.state == "FAILED"
    assert out.state != "CREATED"
    assert out.github_url is None
    assert out.github_number is None
    assert "GITHUB_PERMISSION_DENIED" in (out.failure_reason or "")
    # the failure_reason echoes GitHub's message but never a credential
    assert not contains_secret(out.failure_reason or "")


def test_review_required_for_protected_branch_without_approval(
    db_session, acceptance_fixture_path, tmp_path
):
    settings = Settings(
        ingestion_local_roots=[str(acceptance_fixture_path.parent)],
        artifacts_root=str(tmp_path / "artifacts"),
        github_token=_TOKEN,
        _env_file=None,
    )
    task_id = _verified_task(db_session, settings, acceptance_fixture_path)
    repo = RepositoryRepository(db_session).get(
        TaskRepository(db_session).get(task_id).repository_id
    )
    repo.source_type = "GITHUB"
    repo.url_or_path = "https://github.com/octo/demo"
    repo.default_branch = "main"
    db_session.commit()

    calls: list[str] = []
    out = pr_service.create_pr(
        db_session,
        settings=settings,
        task_id=task_id,
        github_client=_mock_client(
            lambda r: (calls.append(r.url.path), httpx.Response(500))[1]
        ),
        approved=False,
    )
    assert out.mode == "GITHUB"
    assert out.state == "DRAFTED"
    assert "REVIEW_REQUIRED" in (out.failure_reason or "")
    assert calls == []  # nothing was pushed
