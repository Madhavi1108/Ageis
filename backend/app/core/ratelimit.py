"""In-process API rate limiter (docs/SECURITY_MODEL.md, Phase 26).

A dependency-free fixed-window counter with a burst allowance, keyed by API key
(``X-API-Key`` / ``Authorization: Bearer``) when present, else client IP. Good
enough to blunt a single misbehaving client / accidental loop on a
single-process deployment; a multi-process / distributed deployment would swap
this for a shared store (documented follow-up).
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

_WINDOW_S = 60.0


@dataclass
class _Bucket:
    window_start: float
    count: int = 0


@dataclass
class RateLimiter:
    per_minute: int
    burst: int = 0
    _buckets: dict[str, _Bucket] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _last_sweep: float = 0.0

    @property
    def limit(self) -> int:
        return self.per_minute + self.burst

    def check(self, key: str, *, now: float | None = None) -> tuple[bool, int]:
        """Return ``(allowed, retry_after_seconds)``. ``retry_after`` is 0 when allowed."""
        now = time.monotonic() if now is None else now
        with self._lock:
            self._maybe_sweep(now)
            b = self._buckets.get(key)
            if b is None or now - b.window_start >= _WINDOW_S:
                self._buckets[key] = _Bucket(window_start=now, count=1)
                return True, 0
            if b.count < self.limit:
                b.count += 1
                return True, 0
            return False, max(1, int(_WINDOW_S - (now - b.window_start)) + 1)

    def _maybe_sweep(self, now: float) -> None:
        if now - self._last_sweep < _WINDOW_S:
            return
        self._last_sweep = now
        stale = [
            k for k, v in self._buckets.items() if now - v.window_start >= _WINDOW_S
        ]
        for k in stale:
            del self._buckets[k]
