"""Environment-variable allowlist for anything AEGIS spawns
(docs/SECURITY_MODEL.md Section 2 "credential / env-var theft", ADR-0010/0011).

The Docker sandbox already gets an empty environment; this is also used to
scrub ``os.environ`` before it reaches the *local* fake-sandbox subprocess so a
stray ``AWS_SECRET_ACCESS_KEY`` / ``ANTHROPIC_API_KEY`` in the dev shell never
enters a pytest run.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

# What a container test run legitimately needs -- nothing that can carry a secret.
SANDBOX_ENV_ALLOWLIST: tuple[str, ...] = ("LANG", "LC_ALL", "PYTHONHASHSEED")

# Substring/prefix patterns for env var NAMES that may carry a credential. Used
# by the local fake-sandbox runner, which -- unlike the Docker sandbox -- keeps
# most of the host env so the interpreter starts, but must never forward a
# secret. This is a denylist by design (isolation is Docker's job here; this
# just stops accidental credential leakage into a trusted-fixture pytest run).
_SECRET_NAME_RE = re.compile(
    r"(KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|SESSION|COOKIE|AUTH|"
    r"PRIVATE|CERT|SIGNING|ACCESS_ID|CLIENT_ID|CLIENT_SECRET)",
    re.IGNORECASE,
)
_SECRET_NAME_PREFIXES = (
    "AWS_",
    "AZURE_",
    "GCP_",
    "GOOGLE_",
    "ANTHROPIC",
    "OPENAI",
    "GITHUB_",
    "GH_",
    "AEGIS_API_KEYS",
    "AEGIS_GITHUB_TOKEN",
    "DATABASE_URL",
    "AEGIS_DATABASE_URL",
)


def scrub_env(
    src: Mapping[str, str], *, allow: tuple[str, ...] = SANDBOX_ENV_ALLOWLIST
) -> dict[str, str]:
    """Return only the ``allow``-listed keys of ``src`` (case-sensitive).

    This is the strict container path -- the Docker sandbox gets essentially
    nothing.
    """
    return {k: v for k, v in src.items() if k in allow}


def _is_secret_name(name: str) -> bool:
    upper = name.upper()
    if upper.startswith(_SECRET_NAME_PREFIXES):
        return True
    return bool(_SECRET_NAME_RE.search(name))


def scrub_secret_env(src: Mapping[str, str]) -> dict[str, str]:
    """Return ``src`` minus any variable whose *name* looks credential-shaped.

    For the local fake-sandbox subprocess: keep PATH / loader vars / locale so
    pytest runs, drop `*_API_KEY`, `*_TOKEN`, `AWS_*`, `ANTHROPIC*`, the DB URL,
    etc.
    """
    return {k: v for k, v in src.items() if not _is_secret_name(k)}
