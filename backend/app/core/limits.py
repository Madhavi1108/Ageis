"""Central place for size/timeout/resource constants.

See docs/AEGIS_IMPLEMENTATION_PLAN.md Section 10. Later phases (ingestion,
sandbox execution, AI calls) add their own limits here rather than
scattering magic numbers through the codebase; Phase 2 establishes the
module with the one limit it actually enforces.
"""

from __future__ import annotations

from app.core.config import Settings


def max_request_body_bytes(settings: Settings) -> int:
    """Maximum accepted size, in bytes, of an incoming HTTP request body."""
    return settings.request_max_body_bytes
