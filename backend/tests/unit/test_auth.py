"""Phase 21 unit: the require_role dependency."""

from __future__ import annotations

import pytest
from starlette.requests import Request

from app.core.auth import (
    AuthRequiredError,
    ForbiddenError,
    Principal,
    Role,
    require_role,
)
from app.core.config import Settings


def _req(headers: dict[str, str]) -> Request:
    raw = [(k.lower().encode(), v.encode()) for k, v in headers.items()]
    return Request({"type": "http", "method": "POST", "headers": raw, "path": "/x"})


def _run(dep, headers, settings):
    return dep.__wrapped__(_req(headers), settings) if hasattr(dep, "__wrapped__") else dep(_req(headers), settings)


def test_disabled_auth_is_a_noop_admin():
    dep = require_role(Role.OPERATOR)
    p = dep(_req({}), Settings(_env_file=None, auth_enabled=False))
    assert isinstance(p, Principal) and p.role == Role.ADMIN


def test_missing_key_when_enabled_is_401():
    dep = require_role(Role.OPERATOR)
    with pytest.raises(AuthRequiredError):
        dep(_req({}), Settings(_env_file=None, auth_enabled=True, api_keys={"k": "operator"}))


def test_insufficient_role_is_403():
    dep = require_role(Role.APPROVER)
    s = Settings(_env_file=None, auth_enabled=True, api_keys={"v": "viewer"})
    with pytest.raises(ForbiddenError):
        dep(_req({"x-api-key": "v"}), s)


def test_sufficient_role_returns_principal():
    dep = require_role(Role.OPERATOR)
    s = Settings(_env_file=None, auth_enabled=True, api_keys={"op": "operator"})
    p = dep(_req({"x-api-key": "op"}), s)
    assert p.role == Role.OPERATOR


def test_bearer_header_is_accepted():
    dep = require_role(Role.VIEWER)
    s = Settings(_env_file=None, auth_enabled=True, api_keys={"tok": "viewer"})
    p = dep(_req({"authorization": "Bearer tok"}), s)
    assert p.role == Role.VIEWER


def test_role_ordering():
    assert Role.VIEWER < Role.OPERATOR < Role.APPROVER < Role.ADMIN
    assert Role.from_str("approver") is Role.APPROVER
