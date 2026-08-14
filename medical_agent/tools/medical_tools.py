"""Agent tools: knowledge-graph search, generated Cypher, and web search.

Two cross-cutting concerns live here:

1. Tracing. Each tool publishes TOOL_STARTED / TOOL_COMPLETED to the request-scoped
   event bus, which is what drives the live pipeline view in the UI. Instrumenting
   the tools directly (rather than relying on CrewAI callbacks) keeps the trace
   under our control and independent of framework internals.

2. Degradation. Graph-backed tools return an explicit "unavailable" string instead
   of raising when Neo4j is paused, so the agent can route around them.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import time
from datetime import datetime, timedelta
from typing import Any

from crewai.tools import BaseTool
from pydantic import BaseModel, Field, field_validator

from medical_agent.config import Config
from medical_agent.graph.client import get_gateway
from medical_agent.utils.events import EventType, emit

try:  # ddgs is the maintained successor to duckduckgo-search
    from ddgs import DDGS
except ImportError:  # pragma: no cover - fallback for older installs
    from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)

GRAPH_UNAVAILABLE = (
    "Knowledge graph unavailable. Answer from web search and general knowledge, "
    "and state that graph-backed verification was not possible."
)

_TOOL_CACHE: dict[str, tuple[str, datetime]] = {}
_CACHE_TTL = timedelta(hours=1)

# Clauses that mutate or administer the database. Generated Cypher is derived from
# user input, so it is treated as untrusted regardless of the prompt's instructions.
_WRITE_CLAUSE = re.compile(
    r"\b(CREATE|MERGE|DELETE|DETACH|SET|REMOVE|DROP|LOAD\s+CSV|FOREACH|"
    r"CALL\s*\{|apoc\.|db\.|dbms\.|USING\s+PERIODIC)\b",
    re.IGNORECASE,
)


def _cache_key(tool_name: str, query: str) -> str:
    return hashlib.md5(f"{tool_name}:{query.lower().strip()}".encode()).hexdigest()


def _check_cache(tool_name: str, query: str) -> str | None:
    key = _cache_key(tool_name, query)
    entry = _TOOL_CACHE.get(key)
    if entry is None:
        return None
    result, stamped = entry
    if datetime.now() - stamped < _CACHE_TTL:
        return result
    del _TOOL_CACHE[key]
    return None


def _set_cache(tool_name: str, query: str, result: str) -> None:
    _TOOL_CACHE[_cache_key(tool_name, query)] = (result, datetime.now())


def _run_coroutine(coro):
    """Run a coroutine from sync tool code, whether or not a loop is running.

    CrewAI invokes tools synchronously from a worker thread. If that thread happens
    to have a running loop, nest_asyncio lets us reenter it.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    import nest_asyncio

    nest_asyncio.apply()
    return asyncio.run(coro)


class SearchInput(BaseModel):
    query: str = Field(description="The search query string")

    @field_validator("query", mode="before")
    @classmethod
    def coerce_to_string(cls, value: Any) -> str:
        """LLMs sometimes emit the argument schema instead of the argument."""
        if isinstance(value, dict):
            return str(value.get("description", value))
        return str(value)


class TracedTool(BaseTool):
    """Base class emitting trace events around every tool invocation."""

    trace_name: str = "tool"

    def _run(self, query: str) -> str:
        emit(EventType.TOOL_STARTED, tool=self.trace_name, query=query)
        started = time.perf_counter()
        cached = _check_cache(self.trace_name, query)
        if cached is not None:
            emit(
                EventType.TOOL_COMPLETED,
                tool=self.trace_name,
                elapsed_ms=0,
                cached=True,
                ok=True,
                chars=len(cached),
            )
            return cached

        try:
            result = self.execute(query)
            ok = True
        except Exception as exc:  # a failing tool must not kill the run
            logger.exception("%s failed", self.trace_name)
            result, ok = f"{self.trace_name} failed: {exc}", False

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        emit(
            EventType.TOOL_COMPLETED,
            tool=self.trace_name,
            elapsed_ms=elapsed_ms,
            cached=False,
            ok=ok,
            chars=len(result),
        )
        if ok and result and GRAPH_UNAVAILABLE not in result:
            _set_cache(self.trace_name, query, result)
        return result

    def execute(self, query: str) -> str:  # pragma: no cover - overridden
        raise NotImplementedError


class WebSearchTool(TracedTool):
    name: str = "Web Search"
    description: str = "Search the web for medical information not found in the graph."
    args_schema: type[BaseModel] = SearchInput
    trace_name: str = "web_search"

    def execute(self, query: str) -> str:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=3))
        if not results:
            return "No web results found."
        return "\n".join(f"- {r.get('title', '')}: {r.get('body', '')}" for r in results)


class GraphDBTool(TracedTool):
    name: str = "Graph Database Search"
    description: str = (
        "Search the internal medical knowledge graph for drugs, interactions and conditions."
    )
    args_schema: type[BaseModel] = SearchInput
    trace_name: str = "graph_db"

    def execute(self, query: str) -> str:
        return _run_coroutine(self.search(query))

    async def search(self, query: str) -> str:
        """Async entry point, reused by the parallel retrieval path."""
        client = await get_gateway().get_client()
        if client is None:
            return GRAPH_UNAVAILABLE

        from graphiti_core.search.search_config_recipes import COMBINED_HYBRID_SEARCH_RRF

        try:
            results = await client.search_(query, config=COMBINED_HYBRID_SEARCH_RRF)
        except Exception as exc:
            logger.warning("Graph search failed: %s", exc)
            return GRAPH_UNAVAILABLE

        if not results:
            return "No information in graph."

        facts = [f"Fact: {edge.fact}" for edge in (results.edges or [])[:3]]
        if len(facts) < 3:
            for node in (results.nodes or [])[:2]:
                summary = (
                    getattr(node, "summary", None)
                    or getattr(node, "description", None)
                    or getattr(node, "body", "")
                )
                if summary:
                    facts.append(f"Entity: {node.name} - {summary[:150]}...")
        return "\n".join(facts) if facts else "No relevant graph data."


class CypherQueryTool(TracedTool):
    name: str = "Cypher Query Executor"
    description: str = """Execute generated Cypher for complex graph traversals.
    Use for multi-hop drug interactions, or all drugs contraindicated in a condition.
    Examples: 'Find all drugs that interact with Warfarin'."""
    args_schema: type[BaseModel] = SearchInput
    trace_name: str = "cypher"

    _driver: Any | None = None
    _llm_client: Any | None = None

    def _get_driver(self):
        if self._driver is None:
            from neo4j import GraphDatabase

            self._driver = GraphDatabase.driver(
                Config.NEO4J_URI,
                auth=(Config.NEO4J_USER, Config.NEO4J_PASSWORD),
                connection_acquisition_timeout=15,
            )
        return self._driver

    def _get_llm_client(self):
        if self._llm_client is None:
            from groq import Groq

            self._llm_client = Groq(api_key=Config.GROQ_API_KEY)
        return self._llm_client

    def execute(self, query: str) -> str:
        if not Config.graph_configured():
            return GRAPH_UNAVAILABLE

        cypher = self.generate_cypher(query)
        rejection = self.reject_if_unsafe(cypher)
        if rejection:
            logger.warning("Rejected generated Cypher: %s", cypher)
            emit(EventType.TOOL_STARTED, tool="cypher_guard", query=cypher)
            emit(EventType.TOOL_COMPLETED, tool="cypher_guard", ok=False, reason=rejection)
            return f"Generated query rejected by the read-only guard: {rejection}"

        emit(EventType.TOOL_STARTED, tool="cypher_exec", query=cypher)
        started = time.perf_counter()
        try:
            from neo4j import RoutingControl

            driver = self._get_driver()
            # Read routing is defence in depth: a write that slipped past the guard
            # is rejected by the server when routed to a read replica.
            records, _, _ = driver.execute_query(
                cypher,
                routing_=RoutingControl.READ,
                database_=Config.NEO4J_DATABASE,
                timeout=20,
            )
        except Exception as exc:
            logger.warning("Cypher execution failed: %s", exc)
            emit(EventType.TOOL_COMPLETED, tool="cypher_exec", ok=False, error=str(exc))
            return GRAPH_UNAVAILABLE

        rows = [dict(record) for record in records]
        emit(
            EventType.TOOL_COMPLETED,
            tool="cypher_exec",
            ok=True,
            elapsed_ms=int((time.perf_counter() - started) * 1000),
            rows=len(rows),
        )
        if not rows:
            return "No matching data found in graph."
        return self.format_results(rows)

    @staticmethod
    def reject_if_unsafe(cypher: str) -> str | None:
        """Return a reason when the generated Cypher is not a plain read.

        Generated Cypher derives from user text, so it is untrusted input no matter
        what the generating prompt asked for.
        """
        if not cypher or not cypher.strip():
            return "empty query"
        match = _WRITE_CLAUSE.search(cypher)
        if match:
            return f"non-read clause '{match.group(0).strip()}'"
        if ";" in cypher.strip().rstrip(";"):
            return "multiple statements"
        return None

    def generate_cypher(self, query: str) -> str:
        schema = """
        Nodes:
         - Entity (properties: name, summary)
         - Episodic (properties: content, source)
         - Community (properties: name, summary)
        Relationships:
         - (:Entity)-[:RELATES_TO {fact: "..."}]->(:Entity)
         - (:Episodic)-[:MENTIONS]->(:Entity)
        """
        prompt = f"""You are an expert Neo4j Cypher query generator.

Database schema:
{schema}

Generate a read-only Cypher query for: "{query}"

Rules:
1. Return ONLY the Cypher query. No markdown, no explanation.
2. READ ONLY. Never emit CREATE, MERGE, SET, DELETE, REMOVE, DROP or CALL procedures.
3. Case-insensitive matching: toLower(n.name) CONTAINS toLower('term').
4. Search the name and summary properties of Entity nodes.
5. Always LIMIT to 20 and always RETURN DISTINCT.
6. With UNION, alias columns identically across all parts.
7. For interactions or contraindications, filter the 'fact' property of RELATES_TO
   in a WHERE clause, never inside the relationship pattern.
"""
        try:
            completion = self._get_llm_client().chat.completions.create(
                model=Config.GROQ_MODEL_NAME,
                messages=[
                    {"role": "system", "content": "You write read-only Cypher queries."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=500,
            )
            cypher = completion.choices[0].message.content.strip()
            if cypher.startswith("```"):
                cypher = cypher.replace("```cypher", "").replace("```", "").strip()
            return cypher
        except Exception as exc:
            logger.warning("Cypher generation failed: %s", exc)
            safe_term = re.sub(r"[^\w\s-]", "", query)[:80]
            return (
                "MATCH (n:Entity) WHERE toLower(n.name) CONTAINS toLower($term) "
                "RETURN DISTINCT n.name AS Name, n.summary AS Info LIMIT 10"
            ).replace("$term", f"'{safe_term}'")

    @staticmethod
    def format_results(rows: list[dict]) -> str:
        seen, unique = set(), []
        for row in rows:
            marker = tuple(sorted((k, str(v)) for k, v in row.items()))
            if marker not in seen:
                seen.add(marker)
                unique.append(row)

        lines = []
        for index, row in enumerate(unique, 1):
            lines.append(f"Result {index}:")
            lines.extend(f"  - {key}: {value}" for key, value in row.items())
            lines.append("")
        return "\n".join(lines)


web_search_tool = WebSearchTool()
graph_db_tool = GraphDBTool()
cypher_query_tool = CypherQueryTool()
