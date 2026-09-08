"""Pick the sandbox runner for the configured ``sandbox_mode``.

``docker`` (default) -> ``DockerSandboxRunner`` (hardened container; Docker
absent -> ``PARTIALLY_SUPPORTED``, never a host fallback).
``fake``             -> ``LocalSubprocessRunner`` (pytest as a local subprocess;
                        trusted fixtures ONLY -- see its docstring).

Both expose the same ``run_tests(ws_root: Path, test_command: list[str]) ->
TestExecutionRun``.
"""

from __future__ import annotations

from app.core.config import Settings
from app.sandbox.resource_limits import ResourceLimits
from app.sandbox.runner import DockerSandboxRunner, LocalSubprocessRunner


def build_runner(
    settings: Settings,
    *,
    image: str | None = None,
    limits: ResourceLimits | None = None,
):
    if settings.sandbox_mode == "fake":
        return LocalSubprocessRunner(timeout_s=float(settings.sandbox_wall_clock_s))
    return DockerSandboxRunner(
        image=image or settings.sandbox_image,
        limits=limits or ResourceLimits(),
        image_digest=settings.sandbox_image_digest,
        tmpfs_bytes=settings.sandbox_tmpfs_bytes,
    )
