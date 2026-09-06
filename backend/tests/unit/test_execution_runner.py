"""Phase 12 runner: Docker-unavailable degrades to PARTIALLY_SUPPORTED (no
Docker daemon required for this -- it's this dev environment's actual state);
the PASS/FAIL/TIMEOUT/INFRA_ERROR paths are exercised with a monkeypatched
docker_backend so no real daemon is needed for those either.
"""

from __future__ import annotations

from app.sandbox import docker_backend
from app.sandbox.docker_backend import ContainerRunResult, DockerUnavailableError
from app.sandbox.resource_limits import ResourceLimits
from app.sandbox.runner import DockerSandboxRunner


def test_docker_unavailable_is_partially_supported(tmp_path, monkeypatch):
    monkeypatch.setattr(
        docker_backend,
        "get_client",
        lambda: (_ for _ in ()).throw(DockerUnavailableError("no daemon")),
    )
    runner = DockerSandboxRunner()
    result = runner.run_tests(tmp_path, ["test_x.py"])
    assert result.outcome == "PARTIALLY_SUPPORTED"
    assert "docker unavailable" in result.reason


def test_real_docker_absent_in_this_environment_is_partially_supported(tmp_path):
    """Sanity check against the real docker_backend -- this dev environment
    genuinely has no daemon, so this exercises the true code path without
    mocking anything."""
    runner = DockerSandboxRunner()
    result = runner.run_tests(tmp_path, ["test_x.py"])
    assert result.outcome == "PARTIALLY_SUPPORTED"


def _fake_client():
    return object()


def test_timeout_reports_timeout_outcome(tmp_path, monkeypatch):
    monkeypatch.setattr(docker_backend, "get_client", _fake_client)
    monkeypatch.setattr(
        docker_backend,
        "run_and_collect",
        lambda client, kwargs, *, wall_clock_s: ContainerRunResult(
            exit_code=-1, timed_out=True, logs="hung"
        ),
    )
    runner = DockerSandboxRunner(limits=ResourceLimits(wall_clock_s=5))
    result = runner.run_tests(tmp_path, ["test_x.py"])
    assert result.outcome == "TIMEOUT"
    assert "5s" in result.reason
    assert result.stdout == "hung"


def test_no_report_produced_is_infra_error(tmp_path, monkeypatch):
    monkeypatch.setattr(docker_backend, "get_client", _fake_client)
    monkeypatch.setattr(
        docker_backend,
        "run_and_collect",
        lambda client, kwargs, *, wall_clock_s: ContainerRunResult(
            exit_code=0, timed_out=False, logs="ran but no report"
        ),
    )
    runner = DockerSandboxRunner()
    result = runner.run_tests(tmp_path, ["test_x.py"])
    assert result.outcome == "INFRA_ERROR"
    assert "no test report" in result.reason


def test_infra_exception_during_run_is_infra_error(tmp_path, monkeypatch):
    monkeypatch.setattr(docker_backend, "get_client", _fake_client)

    def _boom(client, kwargs, *, wall_clock_s):
        raise RuntimeError("connection reset")

    monkeypatch.setattr(docker_backend, "run_and_collect", _boom)
    runner = DockerSandboxRunner()
    result = runner.run_tests(tmp_path, ["test_x.py"])
    assert result.outcome == "INFRA_ERROR"
    assert "connection reset" in result.reason


def test_parsed_report_all_pass_is_pass(tmp_path, monkeypatch):
    report = tmp_path / ".aegis_report.xml"
    report.write_text(
        '<testsuites><testsuite><testcase classname="t" name="test_a" '
        'file="test_a.py" /></testsuite></testsuites>',
        encoding="utf-8",
    )
    monkeypatch.setattr(docker_backend, "get_client", _fake_client)
    monkeypatch.setattr(
        docker_backend,
        "run_and_collect",
        lambda client, kwargs, *, wall_clock_s: ContainerRunResult(
            exit_code=0, timed_out=False, logs="ok"
        ),
    )
    runner = DockerSandboxRunner()
    result = runner.run_tests(tmp_path, ["test_a.py"])
    assert result.outcome == "PASS"
    assert result.results[0].test_id == "test_a.py::test_a"
