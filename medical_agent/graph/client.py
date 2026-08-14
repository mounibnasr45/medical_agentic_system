"""Graphiti/Neo4j access with explicit availability handling.

The deployed demo runs against Neo4j AuraDB Free, which pauses after a few days of
inactivity. A paused database must degrade the answer, not break the request, so
all graph access goes through a gateway that:

  - owns a single long-lived Graphiti client (the previous implementation built and
    closed one per call, which is both slow and unsafe under concurrency),
  - tracks availability, and
  - refuses to retry a failed connection for a cooldown window, so one paused
    database cannot add a connect-timeout to every subsequent request.

Callers ask for a client and get `None` when the graph is unusable. They are
expected to say so in their result rather than raise.
"""

from __future__ import annotations

import asyncio
import logging
import time

from medical_agent.config import Config

logger = logging.getLogger(__name__)

# Aura resume takes tens of seconds; do not retry more often than this.
_RETRY_COOLDOWN_SECONDS = 30.0


class GraphGateway:
    """Single point of access to the knowledge graph."""

    def __init__(self) -> None:
        self._client = None
        self._lock = asyncio.Lock()
        self._last_failure_at: float | None = None
        self._last_error: str | None = None

    @property
    def configured(self) -> bool:
        return Config.graph_configured()

    @property
    def last_error(self) -> str | None:
        return self._last_error

    def _in_cooldown(self) -> bool:
        if self._last_failure_at is None:
            return False
        return (time.monotonic() - self._last_failure_at) < _RETRY_COOLDOWN_SECONDS

    def _build_llm_client(self):
        """LLM used by Graphiti for entity and relationship extraction.

        Defaults to Gemini because extraction prompts are large: roughly 19k
        tokens per episode, against a 12k tokens-per-minute ceiling on Groq's
        free tier. That is a single oversized request, not a pacing problem, so
        no amount of retrying or delay makes it succeed.
        """
        if Config.GRAPH_LLM_PROVIDER == "groq":
            from medical_agent.graph.groq_client import GroqClient

            return GroqClient(api_key=Config.GROQ_API_KEY, model=Config.GROQ_MODEL_NAME)

        from graphiti_core.llm_client.config import LLMConfig
        from graphiti_core.llm_client.gemini_client import GeminiClient

        return GeminiClient(
            config=LLMConfig(
                api_key=Config.GOOGLE_API_KEY,
                model=Config.GEMINI_MODEL_NAME,
                small_model=Config.GEMINI_MODEL_NAME,
                temperature=0.0,
            )
        )

    def _build_embedder(self):
        """Gemini embeddings over the API.

        Replaces a local sentence-transformers model: that pulled in torch, which
        does not fit the deployment's 512MB memory ceiling.
        """
        from graphiti_core.embedder.gemini import GeminiEmbedder, GeminiEmbedderConfig

        return GeminiEmbedder(
            config=GeminiEmbedderConfig(
                api_key=Config.GOOGLE_API_KEY,
                embedding_model=Config.GEMINI_EMBEDDING_MODEL,
                # Passed explicitly: graphiti reads EMBEDDING_DIM from the environment
                # at import time, which is too fragile to depend on.
                embedding_dim=Config.EMBEDDING_DIM,
            )
        )

    async def get_client(self):
        """Return a connected Graphiti client, or None when unavailable."""
        if not self.configured:
            self._last_error = "graph not configured"
            return None

        if self._client is not None:
            return self._client

        if self._in_cooldown():
            return None

        async with self._lock:
            # Another coroutine may have connected while we waited.
            if self._client is not None:
                return self._client
            if self._in_cooldown():
                return None

            try:
                from graphiti_core import Graphiti
                from graphiti_core.driver.neo4j_driver import Neo4jDriver

                # Built explicitly rather than passing uri/user/password to
                # Graphiti: that path hardcodes the database name to "neo4j",
                # which is wrong for instances that name it after the instance id.
                client = Graphiti(
                    graph_driver=Neo4jDriver(
                        uri=Config.NEO4J_URI,
                        user=Config.NEO4J_USER,
                        password=Config.NEO4J_PASSWORD,
                        database=Config.NEO4J_DATABASE,
                    ),
                    llm_client=self._build_llm_client(),
                    embedder=self._build_embedder(),
                )
                await self._verify(client)
                self._client = client
                self._last_failure_at = None
                self._last_error = None
                logger.info("Graph connected: %s", Config.NEO4J_URI)
                return client
            except Exception as exc:
                self._last_failure_at = time.monotonic()
                self._last_error = str(exc)
                logger.warning("Graph unavailable (%s); degrading to web + LLM", exc)
                return None

    async def _verify(self, client) -> None:
        """Fail fast if the database is paused or unreachable."""
        driver = getattr(client, "driver", None)
        if driver is None:
            return
        for attr in ("execute_query", "verify_connectivity"):
            method = getattr(driver, attr, None)
            if method is None:
                continue
            result = method("RETURN 1") if attr == "execute_query" else method()
            if asyncio.iscoroutine(result):
                await asyncio.wait_for(result, timeout=15)
            return

    async def _health(self) -> dict:
        """Status for /health. Never raises."""
        if not Config.GRAPH_ENABLED:
            return {"status": "disabled"}
        if not self.configured:
            return {"status": "not_configured"}
        client = await self.get_client()
        if client is None:
            return {"status": "unavailable", "detail": self._last_error}
        return {"status": "connected"}

    async def close(self) -> None:
        if self._client is not None:
            try:
                await self._client.close()
            except Exception as exc:
                logger.debug("Error closing graph client: %s", exc)
            self._client = None

    async def health(self) -> dict:
        """Status for /health, evaluated on the graph loop."""
        from medical_agent.graph import loop as graph_loop

        try:
            return await graph_loop.run_async(self._health(), timeout=30)
        except Exception as exc:  # never fail the health check itself
            return {"status": "unavailable", "detail": str(exc)}

    async def available(self) -> bool:
        from medical_agent.graph import loop as graph_loop

        try:
            return await graph_loop.run_async(self.get_client(), timeout=30) is not None
        except Exception:
            return False


_gateway = GraphGateway()


def get_gateway() -> GraphGateway:
    return _gateway


async def get_graphiti_client():
    """Compatibility helper. Returns None when the graph is unavailable."""
    return await _gateway.get_client()
