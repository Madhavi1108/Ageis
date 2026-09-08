"""Shared base classes for API schemas (Phase 26).

``StrictModel`` rejects unknown fields so a typo'd or injected key in a request
body is a ``422`` instead of being silently dropped (docs/SECURITY_MODEL.md
Section 3). Request-body models inherit it; response / internal models keep
Pydantic's default ``extra="ignore"``.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
