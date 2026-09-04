"""Build metadata surfaced by GET /version."""

from __future__ import annotations

import os
import subprocess
from functools import lru_cache

APP_VERSION = "0.2.0"


@lru_cache
def get_git_sha() -> str | None:
    """Best-effort short git sha of the running checkout, or None if unavailable."""
    env_sha = os.environ.get("AEGIS_GIT_SHA")
    if env_sha:
        return env_sha
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2,
            check=True,
        )
        return result.stdout.strip() or None
    except Exception:
        return None


def get_version_info() -> dict[str, str | None]:
    return {"version": APP_VERSION, "git_sha": get_git_sha()}
