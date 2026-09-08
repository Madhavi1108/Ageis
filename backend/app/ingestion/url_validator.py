"""Backwards-compatible re-export shim.

The SSRF / URL / local-path guard moved to ``app/core/security/ssrf.py`` in
Phase 26 (``core/security`` is now the single enforcement point, per ADR-0011).
Existing importers of ``app.ingestion.url_validator`` keep working unchanged.
"""

from __future__ import annotations

from app.core.security.ssrf import (
    ParsedGitHubUrl,
    validate_local_path,
    validate_remote_url,
)

__all__ = ["ParsedGitHubUrl", "validate_local_path", "validate_remote_url"]
