"""Subprocess allowlist (docs/SECURITY_MODEL.md Section 2 "command injection").

``core.security.subprocess_guard.guarded_run`` is the only sanctioned way for
``app/`` to spawn a process: no ``shell=``, args as a list, ``argv[0]`` on the
allowlist. A codebase scan asserts nothing bypasses it.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

from app.core.security.subprocess_guard import (
    ALLOWED_EXECUTABLES,
    SubprocessNotAllowedError,
    guarded_run,
)

APP_DIR = Path(__file__).resolve().parents[2] / "app"
# the modules allowed to import/use `subprocess` directly
_SANCTIONED = {
    APP_DIR / "core" / "security" / "subprocess_guard.py",
    APP_DIR / "sandbox" / "runner.py",  # keeps `subprocess.TimeoutExpired`
    APP_DIR / "review" / "static_checks.py",  # keeps `subprocess.SubprocessError`
}


def test_rejects_non_allowlisted_executable():
    with pytest.raises(SubprocessNotAllowedError):
        guarded_run(["rm", "-rf", "/"])
    with pytest.raises(SubprocessNotAllowedError):
        guarded_run(["/bin/sh", "-c", "echo hi"])


def test_rejects_shell_true():
    with pytest.raises(SubprocessNotAllowedError):
        guarded_run(["git", "status"], shell=True)


def test_rejects_string_argv():
    with pytest.raises(SubprocessNotAllowedError):
        guarded_run("git status")  # type: ignore[arg-type]


def test_allows_python_version_probe():
    proc = guarded_run(
        [sys.executable, "-c", "print('ok')"], capture_output=True, text=True
    )
    assert proc.stdout.strip() == "ok"


def test_git_is_on_the_allowlist():
    assert "git" in ALLOWED_EXECUTABLES and "docker" in ALLOWED_EXECUTABLES


def _uses_subprocess_directly(path: Path) -> list[str]:
    """Return offending lines: a bare ``subprocess.run/call/Popen(...)`` or any
    ``shell=True`` keyword."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    bad: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.keyword) and node.arg == "shell":
            if not (isinstance(node.value, ast.Constant) and node.value.value is False):
                bad.append(f"{path.name}:{node.lineno} shell= keyword")
        if isinstance(node, ast.Call):
            func = node.func
            dotted = ""
            if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                dotted = f"{func.value.id}.{func.attr}"
            if dotted in {
                "subprocess.run",
                "subprocess.call",
                "subprocess.Popen",
                "subprocess.check_call",
                "subprocess.check_output",
                "os.system",
                "os.popen",
            }:
                bad.append(f"{path.name}:{node.lineno} {dotted}(...)")
    return bad


def test_no_module_bypasses_the_guard():
    offenders: dict[str, list[str]] = {}
    for py in APP_DIR.rglob("*.py"):
        if py in _SANCTIONED:
            continue
        hits = _uses_subprocess_directly(py)
        if hits:
            offenders[str(py.relative_to(APP_DIR))] = hits
    assert not offenders, f"un-guarded subprocess use: {offenders}"
