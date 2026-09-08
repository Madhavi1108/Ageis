"""Subprocess allowlist (docs/SECURITY_MODEL.md Section 2 "shell execution /
command injection", ADR-0011).

AEGIS spawns exactly three external programs: ``git`` (via GitPython, which
builds its own argv), ``docker`` (via the docker SDK), and ``python`` /
``pytest`` (the local fake-sandbox runner + a couple of build-info calls).
Every direct ``subprocess`` call in ``app/`` goes through :func:`guarded_run`,
which forbids ``shell=`` and asserts ``argv[0]`` is one of the allowed
executables -- so a future edit that interpolates untrusted text into a command
fails loudly instead of executing.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

# basename (no extension) of every program AEGIS is allowed to spawn directly.
ALLOWED_EXECUTABLES: frozenset[str] = frozenset(
    {
        "git",
        "docker",
        "python",
        "python3",
        Path(sys.executable).stem.lower(),  # e.g. "python", "python3.13"
        "pytest",
        "alembic",
        "pip-compile",
        "pip-audit",
        "bandit",
    }
)


class SubprocessNotAllowedError(Exception):
    """A subprocess call was blocked by the allowlist / shell guard."""


def _basename(arg0: str) -> str:
    return Path(arg0).name.lower().removesuffix(".exe")


def guarded_run(argv: list[str], **kwargs: Any) -> "subprocess.CompletedProcess[Any]":
    """``subprocess.run`` with the AEGIS allowlist applied.

    * ``argv`` must be a non-empty list (never a string).
    * ``shell`` must be falsy.
    * ``Path(argv[0]).name`` must be in :data:`ALLOWED_EXECUTABLES`.
    """
    if kwargs.get("shell"):
        raise SubprocessNotAllowedError("shell=True is never allowed")
    if not isinstance(argv, (list, tuple)) or not argv:
        raise SubprocessNotAllowedError(
            f"argv must be a non-empty list, got {type(argv).__name__}"
        )
    exe = _basename(str(argv[0]))
    if exe not in ALLOWED_EXECUTABLES:
        raise SubprocessNotAllowedError(
            f"{exe!r} is not in the subprocess allowlist {sorted(ALLOWED_EXECUTABLES)}"
        )
    return subprocess.run(list(argv), **kwargs)  # noqa: S603 -- allowlisted above
