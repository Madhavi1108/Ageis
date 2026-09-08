"""Central input-validation façade (docs/SECURITY_MODEL.md Section 3, ADR-0011).

Every external input has a validator; this module is the one import site that
names them all, plus :class:`StrictModel` -- the base class request bodies
inherit so an unknown field is a ``422`` instead of being silently dropped.
"""

from __future__ import annotations

from app.core.security.pathjail import PathJailError, safe_join
from app.core.security.ssrf import (
    ParsedGitHubUrl,
    validate_local_path,
    validate_remote_url,
)
from app.schemas._base import StrictModel

__all__ = [
    "StrictModel",
    "safe_join",
    "PathJailError",
    "validate_remote_url",
    "validate_local_path",
    "ParsedGitHubUrl",
]
