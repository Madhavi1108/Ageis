"""API rate limiting (Phase 26, docs/SECURITY_MODEL.md). Opt-in; off by
default so the rest of the suite is unaffected.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.ratelimit import RateLimiter


def test_limiter_allows_up_to_limit_then_blocks():
    rl = RateLimiter(per_minute=3, burst=0)
    t = 1000.0
    assert [rl.check("k", now=t)[0] for _ in range(3)] == [True, True, True]
    allowed, retry_after = rl.check("k", now=t)
    assert allowed is False and retry_after >= 1


def test_limiter_window_resets():
    rl = RateLimiter(per_minute=1, burst=0)
    assert rl.check("k", now=0.0)[0] is True
    assert rl.check("k", now=1.0)[0] is False
    assert rl.check("k", now=61.0)[0] is True  # new window


def test_limiter_is_per_key():
    rl = RateLimiter(per_minute=1, burst=0)
    assert rl.check("a", now=0.0)[0] is True
    assert rl.check("b", now=0.0)[0] is True
    assert rl.check("a", now=0.0)[0] is False


def test_burst_adds_headroom():
    rl = RateLimiter(per_minute=1, burst=2)
    assert [rl.check("k", now=0.0)[0] for _ in range(3)] == [True, True, True]
    assert rl.check("k", now=0.0)[0] is False


def test_middleware_returns_429_with_retry_after(monkeypatch):
    monkeypatch.setenv("AEGIS_RATE_LIMIT_ENABLED", "1")
    monkeypatch.setenv("AEGIS_RATE_LIMIT_PER_MINUTE", "2")
    monkeypatch.setenv("AEGIS_RATE_LIMIT_BURST", "0")
    from app.core.config import get_settings
    from app.main import create_app

    get_settings.cache_clear()
    try:
        client = TestClient(create_app())
        # a path that needs no DB -- the limiter runs before routing, so a 404
        # route still gets rate-limited once the window is full
        responses = [client.get("/__rl_probe__") for _ in range(5)]
    finally:
        get_settings.cache_clear()
    codes = [r.status_code for r in responses]
    assert codes[:2] == [404, 404]  # under the limit -> normal routing (404)
    assert 429 in codes
    limited = next(r for r in responses if r.status_code == 429)
    assert limited.headers.get("Retry-After")
    assert limited.json()["code"] == "RATE_LIMITED"


def test_health_is_exempt_from_rate_limit(monkeypatch):
    monkeypatch.setenv("AEGIS_RATE_LIMIT_ENABLED", "1")
    monkeypatch.setenv("AEGIS_RATE_LIMIT_PER_MINUTE", "1")
    monkeypatch.setenv("AEGIS_RATE_LIMIT_BURST", "0")
    from app.core.config import get_settings
    from app.main import create_app

    get_settings.cache_clear()
    try:
        client = TestClient(create_app())
        codes = [client.get("/healthz").status_code for _ in range(5)]
    finally:
        get_settings.cache_clear()
    assert all(c == 200 for c in codes)
