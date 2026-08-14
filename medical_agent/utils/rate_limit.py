"""Per-IP daily rate limiting.

The public demo puts a paid LLM behind an unauthenticated endpoint, so the quota
is a spend ceiling, not a fairness mechanism.

State is in-process and therefore resets when the service restarts. That is an
accepted trade-off for a free-tier demo: a shared store (Redis) is the production
answer but is not free. Because the deployment runs a single instance kept warm by
a scheduled ping, restarts are rare in practice.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from medical_agent.config import Config


@dataclass(frozen=True)
class Quota:
    """A caller's standing for the current UTC day."""

    limit: int
    used: int
    allowed: bool

    @property
    def remaining(self) -> int:
        return max(0, self.limit - self.used)

    def as_dict(self) -> dict:
        return {
            "limit": self.limit,
            "used": self.used,
            "remaining": self.remaining,
            "resets_at": self.resets_at(),
        }

    @staticmethod
    def resets_at() -> str:
        """ISO timestamp of the next UTC midnight."""
        now = datetime.now(UTC)
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return (midnight + timedelta(days=1)).isoformat().replace("+00:00", "Z")


class DailyRateLimiter:
    """Counts requests per key per UTC day."""

    def __init__(self, limit: int | None = None) -> None:
        self.limit = Config.DAILY_QUERY_LIMIT if limit is None else limit
        self._counts: dict[str, int] = {}
        self._day: date = self._today()
        self._lock = threading.Lock()

    @staticmethod
    def _today() -> date:
        return datetime.now(UTC).date()

    def _roll_over_if_needed(self) -> None:
        today = self._today()
        if today != self._day:
            self._counts.clear()
            self._day = today

    def peek(self, key: str) -> Quota:
        """Current standing without consuming anything."""
        with self._lock:
            self._roll_over_if_needed()
            used = self._counts.get(key, 0)
            return Quota(limit=self.limit, used=used, allowed=used < self.limit)

    def consume(self, key: str) -> Quota:
        """Consume one unit if available.

        Returns a quota whose `allowed` reports whether the caller may proceed.
        Nothing is consumed when the caller is already over the limit.
        """
        with self._lock:
            self._roll_over_if_needed()
            used = self._counts.get(key, 0)
            if used >= self.limit:
                return Quota(limit=self.limit, used=used, allowed=False)
            self._counts[key] = used + 1
            return Quota(limit=self.limit, used=used + 1, allowed=True)

    def reset(self) -> None:
        with self._lock:
            self._counts.clear()
            self._day = self._today()


def client_key(forwarded_for: str | None, fallback: str | None) -> str:
    """Identify the caller.

    Render terminates TLS at a proxy, so the socket peer is always the proxy. The
    left-most X-Forwarded-For entry is the original client.
    """
    if forwarded_for:
        first = forwarded_for.split(",")[0].strip()
        if first:
            return first
    return fallback or "unknown"


_limiter: DailyRateLimiter | None = None


def get_limiter() -> DailyRateLimiter:
    global _limiter
    if _limiter is None:
        _limiter = DailyRateLimiter()
    return _limiter
