"""Phase 12 docker_backend: availability check + run/wait/collect/remove,
against a stub client (no real Docker SDK object needed)."""

from __future__ import annotations

import pytest

from app.sandbox import docker_backend
from app.sandbox.docker_backend import DockerUnavailableError


def test_is_available_false_when_no_daemon():
    # This dev environment genuinely has no Docker daemon.
    assert docker_backend.is_available() is False


def test_get_client_raises_when_no_daemon():
    with pytest.raises(DockerUnavailableError):
        docker_backend.get_client()


class _StubContainer:
    def __init__(self, *, exit_code=0, raise_on_wait=False, logs=b"ok"):
        self._exit_code = exit_code
        self._raise_on_wait = raise_on_wait
        self._logs = logs
        self.killed = False
        self.removed = False

    def wait(self, timeout=None):
        if self._raise_on_wait:
            raise TimeoutError("wait timed out")
        return {"StatusCode": self._exit_code}

    def logs(self):
        return self._logs

    def kill(self):
        self.killed = True

    def remove(self, force=False):
        self.removed = True


class _StubContainers:
    def __init__(self, container):
        self._container = container

    def run(self, **kwargs):
        return self._container


class _StubClient:
    def __init__(self, container):
        self.containers = _StubContainers(container)


def test_run_and_collect_success():
    container = _StubContainer(exit_code=0, logs=b"all good")
    client = _StubClient(container)
    result = docker_backend.run_and_collect(client, {}, wall_clock_s=10)
    assert result.exit_code == 0
    assert result.timed_out is False
    assert result.logs == "all good"
    assert container.removed is True
    assert container.killed is False


def test_run_and_collect_timeout_kills_and_removes():
    container = _StubContainer(raise_on_wait=True, logs=b"hung output")
    client = _StubClient(container)
    result = docker_backend.run_and_collect(client, {}, wall_clock_s=1)
    assert result.timed_out is True
    assert result.exit_code == -1
    assert container.killed is True
    assert container.removed is True


def test_run_and_collect_always_removes_even_if_kill_fails():
    class _NoKillContainer(_StubContainer):
        def kill(self):
            raise RuntimeError("already dead")

    container = _NoKillContainer(raise_on_wait=True)
    client = _StubClient(container)
    result = docker_backend.run_and_collect(client, {}, wall_clock_s=1)
    assert result.timed_out is True
    assert container.removed is True
