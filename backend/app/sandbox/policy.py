"""Docker sandbox policy: the resource caps and isolation flags every
execution uses. See docs/SECURITY_MODEL.md Section 2 (threat -> control
matrix), docs/EXECUTION_MODEL.md Section 4-5, and docs/DECISIONS/ADR-0010.

Fully unit-testable without a running Docker daemon -- this module only
builds the keyword arguments passed to the `docker` SDK's
`containers.run(...)`. Extends backend/aegis/sandbox/policy.py (the Phase 1
reduced version) with `nofile`/`nproc` ulimits, which the walking skeleton
didn't need.
"""

from __future__ import annotations

from typing import Any

from docker.types import Ulimit

from app.sandbox.resource_limits import ResourceLimits

# Env allowlist (docs/SECURITY_MODEL.md Section 2 "credential/env-var theft"):
# only what a Python test run needs, nothing that could carry a secret.
ALLOWED_ENV_KEYS = ("LANG", "LC_ALL", "PYTHONHASHSEED")

# Tag-pinned, not digest-pinned: no image registry/CI publishing pipeline
# exists yet to produce and record a digest (documented open item, same
# status as Phase 1's walking-skeleton image -- see docker/sandbox.Dockerfile).
DEFAULT_IMAGE = "aegis-sandbox:py311"


def build_run_kwargs(
    *,
    image: str,
    command: list[str],
    workspace_host_path: str,
    limits: ResourceLimits = ResourceLimits(),
    extra_env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build the `docker` SDK `containers.run(...)` kwargs implementing the
    full control matrix (docs/EXECUTION_MODEL.md Section 4 step 2):

    - network_mode="none"            -- no network exfiltration
    - cap_drop=["ALL"]                -- minimal Linux capabilities
    - security_opt no-new-privileges -- no privilege escalation
    - pids_limit                     -- fork-bomb protection
    - mem_limit / memswap_limit / nano_cpus -- CPU/memory exhaustion protection
    - ulimits nofile/nproc           -- fd-exhaustion / process-exhaustion protection
    - read_only + tmpfs /tmp         -- filesystem escape protection (only the
                                         workspace bind mount is writable)
    - non-root user                  -- least privilege
    - no Docker socket mounted       -- (never added here) container-escape protection
    """
    env = {k: v for k, v in (extra_env or {}).items() if k in ALLOWED_ENV_KEYS}
    return {
        "image": image,
        "command": command,
        "network_mode": "none",
        "cap_drop": ["ALL"],
        "security_opt": ["no-new-privileges"],
        "pids_limit": limits.pids_limit,
        "mem_limit": f"{limits.memory_mb}m",
        "memswap_limit": f"{limits.memory_mb}m",
        "nano_cpus": int(limits.cpus * 1_000_000_000),
        "ulimits": [
            Ulimit(name="nofile", soft=limits.nofile_limit, hard=limits.nofile_limit),
            Ulimit(name="nproc", soft=limits.nproc_limit, hard=limits.nproc_limit),
        ],
        "read_only": True,
        "tmpfs": {"/tmp": ""},
        "volumes": {workspace_host_path: {"bind": "/workspace", "mode": "rw"}},
        "working_dir": "/workspace",
        "user": "1000:1000",
        "environment": env,
        "detach": True,
        "remove": False,  # removed explicitly after collecting logs (docker_backend.py)
    }
