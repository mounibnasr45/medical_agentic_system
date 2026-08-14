"""The daily quota is the demo's spend ceiling, so its edges are worth pinning."""

from datetime import UTC

from medical_agent.utils.rate_limit import DailyRateLimiter, client_key


def test_consumes_up_to_the_limit_then_refuses():
    limiter = DailyRateLimiter(limit=3)

    assert [limiter.consume("ip").allowed for _ in range(3)] == [True, True, True]

    denied = limiter.consume("ip")
    assert denied.allowed is False
    assert denied.remaining == 0


def test_over_limit_calls_do_not_inflate_the_count():
    """A refused call must not consume, or `used` would grow without bound."""
    limiter = DailyRateLimiter(limit=1)
    limiter.consume("ip")

    first_refusal = limiter.consume("ip")
    second_refusal = limiter.consume("ip")

    assert first_refusal.used == second_refusal.used == 1


def test_callers_are_tracked_independently():
    limiter = DailyRateLimiter(limit=1)

    limiter.consume("1.1.1.1")

    assert limiter.consume("1.1.1.1").allowed is False
    assert limiter.consume("2.2.2.2").allowed is True


def test_peek_reports_without_consuming():
    limiter = DailyRateLimiter(limit=2)

    assert limiter.peek("ip").remaining == 2
    assert limiter.peek("ip").remaining == 2
    assert limiter.consume("ip").remaining == 1


def test_quota_reset_is_in_the_future():
    """Regression: this once returned the current day's midnight, already past."""
    from datetime import datetime

    limiter = DailyRateLimiter(limit=1)
    resets_at = datetime.fromisoformat(
        limiter.peek("ip").as_dict()["resets_at"].replace("Z", "+00:00")
    )

    assert resets_at > datetime.now(UTC)


class TestClientKey:
    """Render terminates TLS at a proxy, so the socket peer is never the client."""

    def test_prefers_the_leftmost_forwarded_address(self):
        assert client_key("203.0.113.9, 10.0.0.1, 10.0.0.2", "10.0.0.1") == "203.0.113.9"

    def test_falls_back_to_the_socket_peer(self):
        assert client_key(None, "198.51.100.7") == "198.51.100.7"

    def test_ignores_an_empty_forwarded_header(self):
        assert client_key("", "198.51.100.7") == "198.51.100.7"

    def test_degrades_to_a_constant_when_nothing_is_known(self):
        assert client_key(None, None) == "unknown"
