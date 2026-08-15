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


def client_key(
    forwarded_for: str | None,
    fallback: str | None,
    trusted_hops: int | None = None,
) -> str:
    """Identify the caller.

    Render terminates TLS at a proxy, so the socket peer is always the proxy and
    the client address has to come from `X-Forwarded-For`. That header is written
    by the caller: each proxy *appends* the address it saw, so everything to the
    left of our own proxies' entries is whatever the client chose to send. Reading
    the left-most entry - the obvious choice, and the one this used to make - lets
    a visitor mint an unused daily allowance per forged address.

    Counting `trusted_hops` from the right lands on the address the outermost
    proxy we control actually observed, which the caller cannot influence. The
    setting has to match the real topology: too high trusts forged entries again,
    too low collapses every visitor onto one proxy address and makes them share a
    single allowance.
    """
    hops = Config.TRUSTED_PROXY_HOPS if trusted_hops is None else trusted_hops

    if hops <= 0:
        # Nothing in front of us, so the header is pure caller input.
        return fallback or "unknown"

    entries = [entry.strip() for entry in (forwarded_for or "").split(",")]
    entries = [entry for entry in entries if entry]
    if entries:
        # A chain shorter than configured means the request did not pass through
        # every expected proxy. Clamping to the left-most entry keeps the closest
        # thing to a client address the header carries.
        return entries[max(0, len(entries) - hops)]
    return fallback or "unknown"


_limiter: DailyRateLimiter | None = None


def get_limiter() -> DailyRateLimiter:
    global _limiter
    if _limiter is None:
        _limiter = DailyRateLimiter()
    return _limiter
