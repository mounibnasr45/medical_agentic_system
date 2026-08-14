"""Parallel retrieval across graph, generated Cypher and web, merged by an LLM.

Complex queries fan out to every relevant source concurrently instead of letting a
single agent try them one at a time. Each source is scored, and a merge step
cross-references them into one answer that notes disagreement.

Previously named "Multi-Context Processing (MCP)". Renamed because MCP now
unambiguously means Model Context Protocol, which this is not.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass

from crewai import LLM

from medical_agent.config import Config
from medical_agent.tools.medical_tools import (
    GRAPH_UNAVAILABLE,
    cypher_query_tool,
    graph_db_tool,
    web_search_tool,
)
from medical_agent.utils.events import EventType, emit

logger = logging.getLogger(__name__)

GRAPH_SOURCES = {"graph_db", "cypher"}


@dataclass
class RetrievalResult:
    """Outcome from a single source."""

    source: str
    content: str
    confidence: float
    latency_ms: int
    error: str | None = None


@dataclass
class MergedRetrieval:
    """Cross-referenced result across all sources."""

    results: list[RetrievalResult]
    merged_content: str
    total_latency_ms: int
    sources_used: list[str]
    confidence_score: float


class ParallelRetriever:
    """Fans a query out to several sources at once and merges the results."""

    def __init__(self) -> None:
        self._merger_llm: LLM | None = None

    @property
    def merger_llm(self) -> LLM:
        if self._merger_llm is None:
            self._merger_llm = LLM(
                model=f"groq/{Config.GROQ_MODEL_NAME}",
                api_key=Config.GROQ_API_KEY,
                temperature=0.2,
                max_tokens=800,
            )
        return self._merger_llm

    async def retrieve(
        self,
        query: str,
        sources: list[str] | None = None,
        timeout: int = 20,
    ) -> MergedRetrieval:
        if sources is None:
            sources = self.select_sources(query)

        if not Config.graph_configured():
            sources = [s for s in sources if s not in GRAPH_SOURCES] or ["web"]

        emit(EventType.STAGE_STARTED, stage="parallel_retrieval", sources=sources)
        started = time.perf_counter()

        runners = {
            "graph_db": self._from_graph,
            "cypher": self._from_cypher,
            "web": self._from_web,
        }
        tasks = [runners[s](query) for s in sources if s in runners]

        try:
            gathered = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True), timeout=timeout
            )
        except TimeoutError:
            logger.warning("Parallel retrieval timed out after %ss", timeout)
            gathered = []

        results = [r for r in gathered if isinstance(r, RetrievalResult)]
        usable = [r for r in results if r.content and r.confidence > 0]
        total_ms = int((time.perf_counter() - started) * 1000)

        merged = await self._merge(query, usable)
        confidence = sum(r.confidence for r in usable) / len(usable) if usable else 0.0

        emit(
            EventType.STAGE_COMPLETED,
            stage="parallel_retrieval",
            elapsed_ms=total_ms,
            ok=bool(usable),
            sources_used=[r.source for r in usable],
            confidence=round(confidence, 3),
        )

        return MergedRetrieval(
            results=results,
            merged_content=merged,
            total_latency_ms=total_ms,
            sources_used=[r.source for r in usable],
            confidence_score=confidence,
        )

    async def _from_graph(self, query: str) -> RetrievalResult:
        started = time.perf_counter()
        emit(EventType.TOOL_STARTED, tool="graph_db", query=query)
        try:
            content = await graph_db_tool.search(query)
            unavailable = content == GRAPH_UNAVAILABLE
            confidence = 0.0 if unavailable else (0.9 if "Fact:" in content else 0.5)
            return self._finish("graph_db", content, confidence, started)
        except Exception as exc:
            return self._failure("graph_db", exc)

    async def _from_cypher(self, query: str) -> RetrievalResult:
        started = time.perf_counter()
        emit(EventType.TOOL_STARTED, tool="cypher", query=query)
        try:
            loop = asyncio.get_running_loop()
            content = await loop.run_in_executor(None, cypher_query_tool.execute, query)
            weak = (not content) or "No matching" in content or content == GRAPH_UNAVAILABLE
            return self._finish("cypher", content, 0.3 if weak else 0.8, started)
        except Exception as exc:
            return self._failure("cypher", exc)

    async def _from_web(self, query: str) -> RetrievalResult:
        started = time.perf_counter()
        emit(EventType.TOOL_STARTED, tool="web", query=query)
        try:
            loop = asyncio.get_running_loop()
            content = await loop.run_in_executor(None, web_search_tool.execute, query)
            return self._finish("web", content, 0.7, started)
        except Exception as exc:
            return self._failure("web", exc)

    @staticmethod
    def _finish(source: str, content: str, confidence: float, started: float) -> RetrievalResult:
        latency = int((time.perf_counter() - started) * 1000)
        emit(
            EventType.TOOL_COMPLETED,
            tool=source,
            elapsed_ms=latency,
            ok=confidence > 0,
            confidence=confidence,
            chars=len(content or ""),
        )
        return RetrievalResult(source, content, confidence, latency)

    @staticmethod
    def _failure(source: str, exc: Exception) -> RetrievalResult:
        logger.warning("%s retrieval failed: %s", source, exc)
        emit(EventType.TOOL_COMPLETED, tool=source, ok=False, error=str(exc))
        return RetrievalResult(source, "", 0.0, 0, error=str(exc))

    @staticmethod
    def select_sources(query: str) -> list[str]:
        lowered = query.lower()
        sources = ["graph_db"]
        if any(w in lowered for w in ("interact", "all", "contraindicat", "together", " and ")):
            sources.append("cypher")
        if any(w in lowered for w in ("latest", "new", "recent", "study", "research")):
            sources.append("web")
        return sources

    async def _merge(self, query: str, results: list[RetrievalResult]) -> str:
        if not results:
            return "No information could be retrieved from any source."

        summary = "\n\n".join(
            f"Source {r.source.upper()} (confidence {r.confidence:.0%}, {r.latency_ms}ms):\n{r.content}"
            for r in results
        )
        prompt = f"""You are a medical information synthesizer.

User query: "{query}"

Information retrieved in parallel from multiple sources:
{summary}

Synthesize one coherent, accurate answer.
- Cross-validate facts across sources.
- Explicitly note any disagreement between sources.
- Prioritise higher-confidence sources.
- Cite which source supports each claim.
- Be concise and medically accurate.
"""
        try:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                None, lambda: self.merger_llm.call([{"role": "user", "content": prompt}])
            )
        except Exception as exc:
            logger.warning("Merge step failed, returning raw sources: %s", exc)
            return f"Sources retrieved (merge unavailable):\n\n{summary}"


_retriever: ParallelRetriever | None = None


def get_parallel_retriever() -> ParallelRetriever:
    global _retriever
    if _retriever is None:
        _retriever = ParallelRetriever()
    return _retriever
