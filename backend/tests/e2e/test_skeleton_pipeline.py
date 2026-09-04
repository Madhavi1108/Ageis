"""The walking skeleton's top-level regression anchor. See
docs/AEGIS_IMPLEMENTATION_PLAN.md Section 9 (Phase 1) "Phase-wise testing".

Three tests always run (no Docker required):
  (a) the acceptance fixture reaches VERIFIED end-to-end via FakeSandboxRunner
  (b) the REAL DockerSandboxRunner, with Docker absent, reaches
      PARTIALLY_SUPPORTED cleanly -- no crash, no host execution of the
      target repository's tests
  (c) the unfixable fixture ends NOT_VERIFIED/SAFE_STOP cleanly after
      exactly 2 repair attempts

A fourth test proves the real happy path through actual Docker; it is marked
`docker` and auto-skips when the daemon is unavailable (it will here).
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import docker
import pytest

from aegis.ai.provider import MockProvider
from aegis.ai.scenarios import register_walking_skeleton_scenarios
from aegis.orchestrator import run_pipeline
from aegis.sandbox.runner import DockerSandboxRunner, FakeSandboxRunner

ROOT = Path(__file__).resolve().parents[3]
ACCEPTANCE_REPO = ROOT / "test-repositories" / "aegis-acceptance"
ACCEPTANCE_TASK = ACCEPTANCE_REPO / "task.md"
UNFIXABLE_REPO = ROOT / "test-repositories" / "fixtures" / "unfixable"
UNFIXABLE_TASK = UNFIXABLE_REPO / "task.md"


def _docker_available() -> bool:
    try:
        client = docker.from_env()
        client.ping()
        return True
    except Exception:  # noqa: BLE001
        return False


def _mock_provider() -> MockProvider:
    provider = MockProvider()
    register_walking_skeleton_scenarios(provider)
    return provider


def test_a_fake_sandbox_reaches_verified(tmp_path):
    report = run_pipeline(
        repo_path=ACCEPTANCE_REPO,
        task_path=ACCEPTANCE_TASK,
        provider=_mock_provider(),
        sandbox=FakeSandboxRunner(),
        record_artifact=False,
    )
    assert report.outcome == "VERIFIED"
    assert report.tests["outcome"] == "PASS"
    assert "invoice.py" in report.diff_text
    assert not report.limitations
    # The exact fix is applied -- this is not a tautological "always passes":
    assert "min(discount, 0.5)" in report.diff_text


def test_b_real_docker_runner_with_docker_absent_is_partially_supported(monkeypatch, tmp_path):
    """Proves the honest degraded path through the REAL sandbox integration
    code (not a test double), and that no host execution of the target
    repo's tests is ever attempted as a fallback."""
    host_pytest_calls: list[list[str]] = []
    real_run = subprocess.run

    def _spy_run(cmd, *args, **kwargs):
        # Record any subprocess invocation that runs pytest against the
        # target repo's own test file -- this must never happen when the
        # real DockerSandboxRunner is used.
        if isinstance(cmd, list) and any("test_invoice.py" in str(part) for part in cmd):
            host_pytest_calls.append(cmd)
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", _spy_run)

    report = run_pipeline(
        repo_path=ACCEPTANCE_REPO,
        task_path=ACCEPTANCE_TASK,
        provider=_mock_provider(),
        sandbox=DockerSandboxRunner(),
        record_artifact=False,
    )

    assert report.outcome == "PARTIALLY_SUPPORTED"
    assert report.limitations
    assert "docker" in report.limitations[0].lower()
    assert host_pytest_calls == [], "the target repo's tests must never run on the host"


def test_c_unfixable_fixture_ends_cleanly_after_two_repair_attempts():
    report = run_pipeline(
        repo_path=UNFIXABLE_REPO,
        task_path=UNFIXABLE_TASK,
        provider=_mock_provider(),  # no canned answer for this task -> generic fallback
        sandbox=FakeSandboxRunner(),
        record_artifact=False,
    )
    assert report.outcome in ("NOT_VERIFIED", "SAFE_STOP")
    assert report.outcome != "VERIFIED"
    assert report.limitations
    assert any("2-attempt" in lim or "exhausted" in lim for lim in report.limitations)


@pytest.mark.docker
@pytest.mark.skipif(not _docker_available(), reason="requires a running Docker daemon")
def test_d_real_docker_reaches_verified_when_docker_is_available():
    """Not exercised in an environment without Docker (it will skip here).
    Present so the full happy path is provable wherever Docker exists."""
    report = run_pipeline(
        repo_path=ACCEPTANCE_REPO,
        task_path=ACCEPTANCE_TASK,
        provider=_mock_provider(),
        sandbox=DockerSandboxRunner(),
        record_artifact=False,
    )
    assert report.outcome == "VERIFIED"
