"""Minimal API-key auth (Phase 21, docs/GOVERNANCE.md Section 4).

Opt-in: with ``auth_enabled=False`` (the default) ``require_role`` is a no-op
that returns an ``admin`` principal, so nothing changes. With it on, a request
must carry ``X-API-Key: <key>`` (or ``Authorization: Bearer <key>``); the key
maps to a role via ``settings.api_keys``; mutating routes declare a minimum
role. GET routes are open in the MVP.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass

from fastapi import Depends, Request, status

from app.core.config import Settings, get_settings
from app.core.errors import AppError


class Role(enum.IntEnum):
    VIEWER = 0
    OPERATOR = 1
    APPROVER = 2
    ADMIN = 3

    @classmethod
    def from_str(cls, value: str) -> "Role":
        return cls[value.upper()]


@dataclass(frozen=True)
class Principal:
    key_id: str
    role: Role


class AuthRequiredError(AppError):
    def __init__(self, message: str = "an API key is required") -> None:
        super().__init__(
            "AUTH_REQUIRED", message, status_code=status.HTTP_401_UNAUTHORIZED
        )


class ForbiddenError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(
            "FORBIDDEN", message, status_code=status.HTTP_403_FORBIDDEN
        )


_ANON_ADMIN = Principal(key_id="anonymous", role=Role.ADMIN)


def _extract_key(request: Request) -> str | None:
    key = request.headers.get("x-api-key")
    if key:
        return key.strip()
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None


def require_role(min_role: Role):
    """Return a dependency that resolves (and authorises) the request's principal."""

    def _dep(
        request: Request, settings: Settings = Depends(get_settings)
    ) -> Principal:
        if not settings.auth_enabled:
            return _ANON_ADMIN
        key = _extract_key(request)
        if not key or key not in settings.api_keys:
            raise AuthRequiredError()
        role = Role.from_str(settings.api_keys[key])
        if role < min_role:
            raise ForbiddenError(
                f"role {role.name} is below the required {min_role.name}"
            )
        return Principal(key_id=key[:8], role=role)

    return _dep


#: Shared route dependencies -- attach to a route's ``dependencies=[...]``.
operator_required = Depends(require_role(Role.OPERATOR))
approver_required = Depends(require_role(Role.APPROVER))
