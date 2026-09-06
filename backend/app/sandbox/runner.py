"""Sandbox execution orchestration. See docs/EXECUTION_MODEL.md Section 4 and
docs/DECISIONS/ADR-0010.

`DockerSandboxRunner` only ever runs test commands inside a Docker container
built from `sandbox/policy.py`'s hardened kwargs. If the Docker daemon is
unavailable, it returns `PARTIALLY_SUPPORTED` -- it NEVER falls back to
running on the host (Absolute Rule 9: "never execute untrusted repository
code directly on the host").
"""

from __future__ import annotations

import time
from pathlib import Path

from app.sandbox import docker_backend
from app.sandbox.policy import DEFAULT_IMAGE, build_run_kwargs
from app.sandbox.resource_limits import ResourceLimits
from app.sandbox.result_parser import parse_junit_xml
from app.schemas.execution import TestExecutionRun

_REPORT_NAME = ".aegis_report.xml"


class DockerSandboxRunner:
    def __init__(
        self, image: str = DEFAULT_IMAGE, limits: ResourceLimits | None = None
    ) -> None:
        self.image = image
        self.limits = limits or ResourceLimits()

    def run_tests(self, ws_root: Path, test_command: list[str]) -> TestExecutionRun:
        """`test_command` is the pytest *arguments* (e.g. ["test_x.py"]), not
        including the `pytest` invocation itself -- the sandbox image
        (docker/sandbox.Dockerfile) provides `pytest` on PATH."""
        command_str = "pytest " + " ".join(test_command)
        started = time.monotonic()

        try:
            client = docker_backend.get_client()
        except docker_backend.DockerUnavailableError as exc:
            return TestExecutionRun(
                command=command_str,
                exit_code=-1,
                outcome="PARTIALLY_SUPPORTED",
                reason=f"docker unavailable: {exc}",
            )

        report_path = ws_root / _REPORT_NAME
        full_command = [
            "pytest",
            *test_command,
            f"--junitxml=/workspace/{_REPORT_NAME}",
        ]
        run_kwargs = build_run_kwargs(
            image=self.image,
            command=full_command,
            workspace_host_path=str(ws_root),
            limits=self.limits,
        )

        try:
            result = docker_backend.run_and_collect(
                client, run_kwargs, wall_clock_s=self.limits.wall_clock_s
            )
        except Exception as exc:  # noqa: BLE001 -- infra failure, not a test failure
            return TestExecutionRun(
                command=command_str,
                exit_code=-1,
                outcome="INFRA_ERROR",
                reason=str(exc),
                duration_ms=int((time.monotonic() - started) * 1000),
            )

        duration_ms = int((time.monotonic() - started) * 1000)

        if result.timed_out:
            return TestExecutionRun(
                command=command_str,
                exit_code=-1,
                outcome="TIMEOUT",
                reason=f"exceeded {self.limits.wall_clock_s}s wall-clock limit",
                stdout=result.logs,
                duration_ms=duration_ms,
            )

        outcomes = parse_junit_xml(report_path)
        if not outcomes:
            return TestExecutionRun(
                command=command_str,
                exit_code=result.exit_code,
                outcome="INFRA_ERROR",
                reason="no test report produced",
                stdout=result.logs,
                duration_ms=duration_ms,
            )
        overall = "PASS" if all(o.outcome == "PASS" for o in outcomes) else "FAIL"
        return TestExecutionRun(
            command=command_str,
            exit_code=result.exit_code,
            outcome=overall,
            results=outcomes,
            stdout=result.logs,
            duration_ms=duration_ms,
        )
