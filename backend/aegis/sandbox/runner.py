"""Sandbox execution. See docs/EXECUTION_MODEL.md Section 4 and
docs/DECISIONS/ADR-0010.

Two implementations:

- `DockerSandboxRunner` is the real thing: it only ever runs test commands
  inside a Docker container built from `sandbox/policy.py`'s hardened
  kwargs. If the Docker daemon is unavailable, it returns
  `PARTIALLY_SUPPORTED` -- it NEVER falls back to running on the host
  (Specification Rule 9: "never execute untrusted repository code directly
  on the host").
- `FakeSandboxRunner` is test-only. It runs pytest as a local subprocess
  against a workspace. This is safe ONLY because every fixture it is used
  against in this repository's test suite is authored by us and contains no
  untrusted code -- it must never be pointed at a real or external
  repository. It exists so the pipeline's actual logic (does the applied
  edit really fix the bug?) can be exercised honestly in this environment,
  without Docker.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Protocol

from aegis.repository.workspace import RWWorkspace
from aegis.sandbox.policy import DEFAULT_IMAGE, ResourceLimits, build_run_kwargs
from aegis.sandbox.result_parser import parse_junit_xml
from aegis.schemas.testing import TestExecutionResult


class SandboxRunner(Protocol):
    def run_tests(
        self, ws: RWWorkspace, test_command: list[str]
    ) -> TestExecutionResult: ...


class DockerSandboxRunner:
    """The real, hardened sandbox. See module docstring."""

    def __init__(
        self, image: str = DEFAULT_IMAGE, limits: ResourceLimits | None = None
    ) -> None:
        self.image = image
        self.limits = limits or ResourceLimits()

    def run_tests(
        self, ws: RWWorkspace, test_command: list[str]
    ) -> TestExecutionResult:
        """`test_command` is the pytest *arguments* (e.g. ["test_invoice.py"]),
        not including the `pytest` invocation itself -- the sandbox image
        (docker/sandbox.Dockerfile) provides `pytest` on PATH."""
        command_str = "pytest " + " ".join(test_command)
        try:
            import docker  # local import: never required unless this path runs

            client = docker.from_env()
            client.ping()
        except Exception as exc:  # noqa: BLE001 -- any failure means "no daemon"
            return TestExecutionResult(
                command=command_str,
                exit_code=-1,
                outcome="PARTIALLY_SUPPORTED",
                reason=f"docker unavailable: {exc}",
            )

        report_name = ".aegis_report.xml"
        report_path = ws.root / report_name
        full_command = ["pytest", *test_command, f"--junitxml=/workspace/{report_name}"]
        kwargs = build_run_kwargs(
            image=self.image,
            command=full_command,
            workspace_host_path=str(ws.root),
            limits=self.limits,
        )

        container = None
        try:
            container = client.containers.run(**kwargs)
            try:
                result = container.wait(timeout=self.limits.wall_clock_s)
                exit_code = result.get("StatusCode", -1)
                timed_out = False
            except Exception:
                exit_code = -1
                timed_out = True
            logs = (
                container.logs().decode("utf-8", errors="replace") if container else ""
            )
        except Exception as exc:  # noqa: BLE001 -- infra failure, not a test failure
            return TestExecutionResult(
                command=command_str,
                exit_code=-1,
                outcome="INFRA_ERROR",
                reason=str(exc),
            )
        finally:
            if container is not None:
                try:
                    container.remove(force=True)
                except Exception:  # noqa: BLE001 -- best-effort cleanup
                    pass

        if timed_out:
            return TestExecutionResult(
                command=command_str,
                exit_code=-1,
                outcome="TIMEOUT",
                reason=f"exceeded {self.limits.wall_clock_s}s wall-clock limit",
                stdout=logs,
            )

        outcomes = parse_junit_xml(report_path)
        if not outcomes:
            return TestExecutionResult(
                command=command_str,
                exit_code=exit_code,
                outcome="INFRA_ERROR",
                reason="no test report produced",
                stdout=logs,
            )
        overall = "PASS" if all(o.outcome == "PASS" for o in outcomes) else "FAIL"
        return TestExecutionResult(
            command=command_str,
            exit_code=exit_code,
            outcome=overall,
            results=outcomes,
            stdout=logs,
        )


class FakeSandboxRunner:
    """Test-only local-subprocess runner. See module docstring -- never use
    against untrusted repository content."""

    def __init__(self, timeout_s: float = 60.0) -> None:
        self.timeout_s = timeout_s

    def run_tests(
        self, ws: RWWorkspace, test_command: list[str]
    ) -> TestExecutionResult:
        """`test_command` is the pytest arguments, same convention as
        DockerSandboxRunner.run_tests (see its docstring)."""
        command_str = "pytest " + " ".join(test_command)
        with tempfile.TemporaryDirectory(prefix="aegis-fake-sandbox-") as tmp:
            report_path = Path(tmp) / "report.xml"
            full_command = [
                sys.executable,
                "-m",
                "pytest",
                *test_command,
                f"--junitxml={report_path}",
            ]
            try:
                proc = subprocess.run(
                    full_command,
                    cwd=ws.root,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_s,
                )
            except subprocess.TimeoutExpired:
                return TestExecutionResult(
                    command=command_str,
                    exit_code=-1,
                    outcome="TIMEOUT",
                    reason=f"exceeded {self.timeout_s}s (fake sandbox)",
                )
            outcomes = parse_junit_xml(report_path)
            if not outcomes:
                return TestExecutionResult(
                    command=command_str,
                    exit_code=proc.returncode,
                    outcome="INFRA_ERROR",
                    reason="no test report produced",
                    stdout=proc.stdout,
                    stderr=proc.stderr,
                )
            overall = "PASS" if all(o.outcome == "PASS" for o in outcomes) else "FAIL"
            return TestExecutionResult(
                command=command_str,
                exit_code=proc.returncode,
                outcome=overall,
                results=outcomes,
                stdout=proc.stdout,
                stderr=proc.stderr,
            )
