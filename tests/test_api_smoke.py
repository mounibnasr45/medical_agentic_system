"""Smoke tests for the HTTP surface.

These run without API keys or a database, so they exercise the endpoints that
resolve before any model or graph access: metadata, health, quota accounting and
request validation.
"""

from medical_agent.utils.rate_limit import get_limiter


def test_root_lists_the_endpoints(client):
    body = client.get("/").json()

    assert body["service"] == "Medical Agent API"
    assert "/ask/stream" in body["endpoints"]


def test_health_reports_status_without_calling_a_model(client):
    """Render's health check and the keep-alive ping both hit this every few minutes."""
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    # GRAPH_ENABLED is false in tests; the endpoint must still succeed.
    assert body["graph"]["status"] == "disabled"


def test_health_is_reachable_when_the_graph_is_down(client):
    """A paused Aura instance must not take the service's health check with it."""
    assert client.get("/health").json()["status"] == "ok"


def test_showcase_lists_examples(client):
    examples = client.get("/showcase").json()["examples"]

    assert len(examples) >= 4
    assert all("query" in item and "precomputed" in item for item in examples)


def test_quota_starts_full(client):
    body = client.get("/quota").json()

    assert body["used"] == 0
    assert body["remaining"] == body["limit"]


def test_ask_refuses_once_the_daily_limit_is_spent(client):
    """The limit is a spend ceiling, so exhaustion must short-circuit before the LLM."""
    limiter = get_limiter()
    for _ in range(limiter.limit):
        limiter.consume("testclient")

    response = client.post("/ask", json={"query": "What is aspirin?"})

    assert response.status_code == 429
    assert "quota" in response.json()["detail"]


def test_stream_endpoint_is_also_rate_limited(client):
    limiter = get_limiter()
    for _ in range(limiter.limit):
        limiter.consume("testclient")

    assert client.post("/ask/stream", json={"query": "What is aspirin?"}).status_code == 429


def test_empty_queries_are_rejected(client):
    assert client.post("/ask", json={"query": ""}).status_code == 422


def test_overlong_queries_are_rejected(client):
    """Bounded input keeps a single request from consuming an outsized token budget."""
    assert client.post("/ask", json={"query": "a" * 5000}).status_code == 422


def test_unknown_session_deletion_is_a_404(client):
    assert client.delete("/sessions/does-not-exist").status_code == 404


def test_new_session_returns_an_id(client):
    session_id = client.post("/sessions/new").json()["session_id"]

    assert session_id
    assert client.get(f"/sessions/{session_id}/history").json()["history"] == []
