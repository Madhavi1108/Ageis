"""``core/security`` -- the single security-enforcement package (ADR-0011,
docs/SECURITY_MODEL.md).

Sub-modules:

* :mod:`redaction`         -- secret-pattern matcher / masker for logs + artifacts
* :mod:`pathjail`          -- ``safe_join`` containment check for every workspace fs op
* :mod:`subprocess_guard`  -- allowlist wrapper around ``subprocess.run`` (no ``shell``)
* :mod:`env_allowlist`     -- env scrub for the sandbox + the local fake runner
* :mod:`ssrf`              -- URL / host / local-path guard for repository ingestion
* :mod:`validate`          -- request-body base model + a re-export façade

``redact`` / ``contains_secret`` are re-exported here because ``core/logging``
and the request-log modules import them as ``from app.core.security import ...``.
The heavier ``ssrf`` / ``validate`` modules (which pull ``app.core.config`` and
``app.ingestion.errors``) are intentionally *not* eagerly imported here -- import
them from their sub-module path to keep this package import cheap and
cycle-free.
"""

from __future__ import annotations

from app.core.security.env_allowlist import (
    SANDBOX_ENV_ALLOWLIST,
    scrub_env,
    scrub_secret_env,
)
from app.core.security.pathjail import PathJailError, safe_join
from app.core.security.redaction import REDACTED, contains_secret, redact
from app.core.security.subprocess_guard import (
    ALLOWED_EXECUTABLES,
    SubprocessNotAllowedError,
    guarded_run,
)

__all__ = [
    "REDACTED",
    "redact",
    "contains_secret",
    "PathJailError",
    "safe_join",
    "SubprocessNotAllowedError",
    "guarded_run",
    "ALLOWED_EXECUTABLES",
    "scrub_env",
    "scrub_secret_env",
    "SANDBOX_ENV_ALLOWLIST",
]
