"""GitHub integration (Phase 19, docs/AEGIS_IMPLEMENTATION_PLAN.md Section 27,
ADR-0015).

A thin ``httpx`` REST client (no heavy SDK). Tokens come from config, are
redacted in every log line (app/core/security.py), and are never persisted.
Every HTTP failure -- auth, permission, not-found, conflict, rate-limit,
network -- maps to a structured ``AppError`` subclass; a pull request is
recorded ``CREATED`` only on a real ``201`` with a stored URL/number
(Spec Section 55 Rule 8).
"""

from __future__ import annotations
