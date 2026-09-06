"""Thin wrapper over the `docker` SDK: availability check, run/wait/collect/
remove with timeouts. Kept separate from runner.py so the orchestration logic
(workspace prep, result assembly, persistence) never touches the SDK
directly. See docs/EXECUTION_MODEL.md Section 4 steps 2-8 and ADR-0010.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class DockerUnavailableError(Exception):
    """No reachable Docker daemon. Callers must map this to
    `PARTIALLY_SUPPORTED` -- never fall back to running on the host
    (Absolute Rule 9)."""


@dataclass
class ContainerRunResult:
    exit_code: int
    timed_out: bool
    logs: str


def is_available() -> bool:
    try:
        import docker

        client = docker.from_env()
        client.ping()
        return True
    except Exception:  # noqa: BLE001 -- any failure means "no daemon"
        return False


def get_client() -> Any:
    """Raises DockerUnavailableError if no daemon is reachable."""
    try:
        import docker

        client = docker.from_env()
        client.ping()
        return client
    except Exception as exc:  # noqa: BLE001 -- any failure means "no daemon"
        raise DockerUnavailableError(str(exc)) from exc


def run_and_collect(client: Any, run_kwargs: dict, *, wall_clock_s: int) -> ContainerRunResult:
    """Run one container to completion (or timeout), always killing +
    removing it before returning -- callers never need their own cleanup
    path for the container itself."""
    container = client.containers.run(**run_kwargs)
    try:
        try:
            result = container.wait(timeout=wall_clock_s)
            exit_code = result.get("StatusCode", -1)
            timed_out = False
        except Exception:  # noqa: BLE001 -- SDK raises on timeout/connection issues
            exit_code = -1
            timed_out = True
            try:
                container.kill()
            except Exception:  # noqa: BLE001 -- may already be dead
                pass
        logs = container.logs().decode("utf-8", errors="replace")
        return ContainerRunResult(exit_code=exit_code, timed_out=timed_out, logs=logs)
    finally:
        try:
            container.remove(force=True)
        except Exception:  # noqa: BLE001 -- best-effort cleanup
            pass
