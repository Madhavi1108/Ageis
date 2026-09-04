"""Secret-pattern matchers shared by the logging redaction filter (core/logging.py).

See docs/AEGIS_IMPLEMENTATION_PLAN.md Section 10 ("redaction filter for known
secret patterns"). This module knows nothing about logging -- it just finds
and masks secret-shaped substrings in arbitrary text, so it can also be
reused later by any component that needs to scrub output before it leaves
the process (e.g. AuditLog's payload_digest inputs).
"""

from __future__ import annotations

import re

REDACTED = "***REDACTED***"

# Each pattern matches a secret-shaped substring; the whole match is replaced.
_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),  # Anthropic/OpenAI-style API keys
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),  # GitHub personal access tokens
    re.compile(r"gh[oprsu]_[A-Za-z0-9]{20,}"),  # other GitHub token prefixes
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._-]{8,}"),  # Authorization: Bearer ...
    re.compile(
        r'(?i)(password|passwd|pwd|secret|token|api[_-]?key)("?\s*[:=]\s*"?)([^\s"&,]{4,})'
    ),
)


def redact(text: str) -> str:
    """Return `text` with any recognized secret-shaped substrings masked."""
    result = text
    for pattern in _SECRET_PATTERNS:
        if pattern.groups:
            result = pattern.sub(
                lambda m: f"{m.group(1)}{m.group(2)}{REDACTED}", result
            )
        else:
            result = pattern.sub(REDACTED, result)
    return result


def contains_secret(text: str) -> bool:
    """True if `text` contains anything matching a known secret pattern."""
    return any(p.search(text) for p in _SECRET_PATTERNS)
