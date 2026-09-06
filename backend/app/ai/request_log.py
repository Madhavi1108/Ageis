"""Redacted AI request logging (docs/AI_AGENT_DESIGN.md Section 3, ADR-0005):
"provider, model id, params, token counts, latency, and a digest of any
untrusted prompt segment -- never the raw body".
"""

from __future__ import annotations

import hashlib
import logging

from app.core.security import redact

_logger = logging.getLogger("app.ai")


def prompt_digest(prompt: str) -> str:
    """A stable, non-reversible fingerprint of a prompt -- lets two runs be
    compared / a prompt be referenced in an audit trail without storing it."""
    return "sha256:" + hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def log_ai_call(
    *,
    provider: str,
    model: str,
    template: str,
    tier: str,
    latency_ms: int,
    prompt: str,
    outcome: str,
    token_counts: dict[str, int] | None = None,
) -> None:
    """Emit one structured record for an AI call. The prompt itself is never
    logged -- only its digest and its length. ``redact`` is applied defensively
    to the small non-prompt fields in case a secret ever reaches them."""
    _logger.info(
        "ai_call",
        extra={
            "ai_provider": provider,
            "ai_model": redact(model),
            "ai_template": template,
            "ai_tier": tier,
            "ai_latency_ms": latency_ms,
            "ai_outcome": outcome,
            "ai_prompt_digest": prompt_digest(prompt),
            "ai_prompt_chars": len(prompt),
            "ai_token_counts": token_counts or {},
        },
    )
