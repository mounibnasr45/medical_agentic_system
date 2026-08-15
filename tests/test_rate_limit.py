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
    """The quota is only as strong as the address it counts against.

    Behind a proxy that address comes from a header the caller writes, so which
    entry gets trusted decides whether the limit holds.
    """

    def test_takes_the_address_the_trusted_proxy_appended(self):
        chain = "203.0.113.9, 198.51.100.7"
        assert client_key(chain, None, trusted_hops=1) == "198.51.100.7"

    def test_a_forged_header_cannot_mint_a_fresh_allowance(self):
        """Regression: reading the left-most entry made the limit opt-in."""
        keys = {
            client_key(f"10.9.9.{n}, 198.51.100.7", None, trusted_hops=1) for n in range(5)
        }

        assert keys == {"198.51.100.7"}

    def test_counts_hops_from_the_right(self):
        chain = "203.0.113.9, 198.51.100.7, 10.0.0.1"
        assert client_key(chain, None, trusted_hops=2) == "198.51.100.7"

    def test_an_unproxied_deployment_ignores_the_header(self):
        assert client_key("203.0.113.9", "198.51.100.7", trusted_hops=0) == "198.51.100.7"

    def test_a_chain_shorter_than_configured_uses_the_leftmost_entry(self):
        assert client_key("198.51.100.7", None, trusted_hops=3) == "198.51.100.7"

    def test_falls_back_to_the_socket_peer(self):
        assert client_key(None, "198.51.100.7", trusted_hops=1) == "198.51.100.7"

    def test_ignores_an_empty_forwarded_header(self):
        assert client_key("", "198.51.100.7", trusted_hops=1) == "198.51.100.7"

    def test_degrades_to_a_constant_when_nothing_is_known(self):
        assert client_key(None, None, trusted_hops=1) == "unknown"
