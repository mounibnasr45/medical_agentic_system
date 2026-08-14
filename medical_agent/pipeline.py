"""Query pipeline: routing, execution and post-processing.

Both the blocking and the streaming endpoint call `run_query`, so there is exactly
one implementation of what happens to a question. The difference between them is
only how the trace is delivered.

Flow:

    showcase lookup -> route -> select mode -> cache check
        -> sequential crew  or  parallel retrieval
        -> optional chain-of-thought -> cache store

CrewAI runs synchronously, so the crew executes in a worker thread. The trace
context is copied into that thread explicitly: `contextvars` do not propagate
through `run_in_executor` on their own, and without the copy every tool event
raised inside the crew would be silently dropped.
"""

from __future__ import annotations

import asyncio
import contextvars
import hashlib
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from medical_agent.config import Config
from medical_agent.graph.client import get_gateway
from medical_agent.utils import showcase
from medical_agent.utils.chain_of_thought import get_cot_processor, render_markdown
from medical_agent.utils.events import EventType, emit
from medical_agent.utils.intelligent_router import QueryAnalysis, get_router
from medical_agent.utils.memory_manager import MemoryManager
from medical_agent.utils.parallel_retrieval import get_parallel_retriever

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 3600
_RESPONSE_CACHE: dict[str, tuple[str, float]] = {}
_CACHE_MAX_ENTRIES = 500

DISCLAIMER = (
    "This is an engineering demonstration, not medical advice. "
    "Consult a qualified healthcare professional before acting on anything here."
)


@dataclass
class QueryResult:
    response: str
    session_id: str
    processing_mode: str
    analysis: dict[str, Any]
    from_cache: bool = False
    from_showcase: bool = False
    latency_ms: int = 0
    sources_used: list[str] = field(default_factory=list)
    confidence: float | None = None
    cot: dict | None = None
    graph_available: bool = False
    disclaimer: str = DISCLAIMER

    def as_dict(self) -> dict:
        return {
            "response": self.response,
            "session_id": self.session_id,
            "processing_mode": self.processing_mode,
            "analysis": self.analysis,
            "from_cache": self.from_cache,
            "from_showcase": self.from_showcase,
            "latency_ms": self.latency_ms,
            "sources_used": self.sources_used,
            "confidence": self.confidence,
            "cot": self.cot,
            "graph_available": self.graph_available,
            "disclaimer": self.disclaimer,
        }


def cache_key(mode: str, session_id: str, query: str) -> str:
    """Key that treats word-order variants of a question as the same question.

    'aspirin warfarin interaction' and 'interaction warfarin aspirin' resolve to
    one entry. Scoped per session because answers depend on conversation context.
    """
    normalised = " ".join(sorted(query.lower().split()))
    raw = f"{mode}:{session_id}:{normalised}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def cache_get(key: str) -> str | None:
    entry = _RESPONSE_CACHE.get(key)
    if entry is None:
        return None
    value, stored_at = entry
    if time.time() - stored_at > CACHE_TTL_SECONDS:
        del _RESPONSE_CACHE[key]
        return None
    return value


def cache_set(key: str, value: str) -> None:
    if len(_RESPONSE_CACHE) >= _CACHE_MAX_ENTRIES:
        oldest = min(_RESPONSE_CACHE, key=lambda k: _RESPONSE_CACHE[k][1])
        del _RESPONSE_CACHE[oldest]
    _RESPONSE_CACHE[key] = (value, time.time())


def cache_clear() -> None:
    _RESPONSE_CACHE.clear()


def should_run_parallel(analysis: QueryAnalysis) -> bool:
    """Whether to fan out to all sources at once instead of running the crew.

    Worth the extra concurrent calls only when the question is complex enough to
    need several sources and specific enough that they will agree or disagree
    usefully.
    """
    return (
        analysis.complexity >= 3
        and len(analysis.suggested_tools) >= 2
        and "interaction" in analysis.intent
    )


async def run_query(
    query: str,
    session_id: str | None = None,
    force_parallel: bool | None = None,
) -> QueryResult:
    """Execute one question end to end."""
    started = time.perf_counter()
    memory = MemoryManager.get_session(session_id)
    emit(EventType.RUN_STARTED, query=query, session_id=memory.session_id)

    # 1. Pre-computed showcase answers cost nothing and return immediately.
    precomputed = showcase.lookup(query)
    if precomputed:
        memory.add_user_message(query)
        memory.add_ai_message(precomputed["response"])
        result = QueryResult(
            response=precomputed["response"],
            session_id=memory.session_id,
            processing_mode=precomputed.get("processing_mode", "SHOWCASE"),
            analysis=precomputed.get("analysis", {}),
            from_showcase=True,
            latency_ms=int((time.perf_counter() - started) * 1000),
            sources_used=precomputed.get("sources_used", []),
            confidence=precomputed.get("confidence"),
            cot=precomputed.get("cot"),
            graph_available=precomputed.get("graph_available", False),
        )
        emit(EventType.ANSWER, text=result.response, from_showcase=True)
        emit(EventType.RUN_COMPLETED, **_completion_payload(result))
        return result

    # 2. Route.
    loop = asyncio.get_running_loop()
    router = get_router()
    analysis = await _in_thread(loop, router.analyze_query, query)

    if not analysis.is_medical:
        message = (
            analysis.rejection_message
            or "I answer medical questions about medications, interactions and conditions."
        )
        memory.add_user_message(query)
        memory.add_ai_message(message)
        emit(EventType.REJECTED, reason=analysis.reasoning, message=message)
        result = QueryResult(
            response=message,
            session_id=memory.session_id,
            processing_mode="REJECTED",
            analysis={"is_medical": False, "reason": analysis.reasoning},
            latency_ms=int((time.perf_counter() - started) * 1000),
        )
        emit(EventType.RUN_COMPLETED, **_completion_payload(result))
        return result

    parallel = should_run_parallel(analysis) if force_parallel is None else force_parallel
    mode = "PARALLEL" if parallel else "SEQUENTIAL"

    # 3. Cache.
    key = cache_key(mode, memory.session_id, query)
    cached = cache_get(key)
    if cached is not None:
        memory.add_user_message(query)
        memory.add_ai_message(cached)
        result = QueryResult(
            response=cached,
            session_id=memory.session_id,
            processing_mode=mode,
            analysis=_analysis_summary(analysis),
            from_cache=True,
            latency_ms=int((time.perf_counter() - started) * 1000),
            graph_available=await _graph_available(),
        )
        emit(EventType.ANSWER, text=cached, from_cache=True)
        emit(EventType.RUN_COMPLETED, **_completion_payload(result))
        return result

    memory.add_user_message(query)
    context = memory.context_for_query()

    # 4. Execute.
    sources: list[str] = []
    confidence: float | None = None

    if parallel:
        retrieval = await get_parallel_retriever().retrieve(query)
        answer = retrieval.merged_content
        sources = retrieval.sources_used
        confidence = retrieval.confidence_score
    else:
        answer = await _run_crew(loop, query, context, analysis)
        sources = analysis.suggested_tools

    # 5. Optional explicit reasoning.
    cot_payload = None
    if analysis.use_chain_of_thought and analysis.cot_reasoning_steps:
        cot_result = await _in_thread(
            loop,
            get_cot_processor().run,
            query,
            analysis.cot_reasoning_steps,
            answer,
        )
        cot_payload = cot_result.as_dict()
        if cot_result.final_answer:
            answer = cot_result.final_answer
        elif cot_result.steps:
            answer = render_markdown(cot_result)

    memory.add_ai_message(answer)
    cache_set(key, answer)

    result = QueryResult(
        response=answer,
        session_id=memory.session_id,
        processing_mode=mode,
        analysis=_analysis_summary(analysis),
        latency_ms=int((time.perf_counter() - started) * 1000),
        sources_used=sources,
        confidence=confidence,
        cot=cot_payload,
        graph_available=await _graph_available(),
    )
    emit(EventType.ANSWER, text=answer)
    emit(EventType.RUN_COMPLETED, **_completion_payload(result))
    return result


async def _run_crew(loop, query: str, context: str, analysis: QueryAnalysis) -> str:
    """Run the crew in a worker thread, carrying the trace context across."""
    from medical_agent.agents.crew import create_medical_crew

    prompt = f"{context}\n\n## Current query:\n{query}" if context else query

    def _kickoff() -> str:
        crew = create_medical_crew(prompt, analysis)
        output = crew.kickoff()
        return output.raw if hasattr(output, "raw") else str(output)

    ctx = contextvars.copy_context()
    return await loop.run_in_executor(None, lambda: ctx.run(_kickoff))


async def _in_thread(loop, fn, *args):
    """Offload a blocking call, preserving the trace context."""
    ctx = contextvars.copy_context()
    return await loop.run_in_executor(None, lambda: ctx.run(fn, *args))


async def _graph_available() -> bool:
    if not Config.graph_configured():
        return False
    return await get_gateway().available()


def _analysis_summary(analysis: QueryAnalysis) -> dict:
    return {
        "is_medical": analysis.is_medical,
        "intent": analysis.intent,
        "complexity": analysis.complexity,
        "confidence": analysis.confidence,
        "agents_used": analysis.required_agents,
        "use_cot": analysis.use_chain_of_thought,
        "reasoning": analysis.reasoning,
    }


def _completion_payload(result: QueryResult) -> dict:
    return {
        "processing_mode": result.processing_mode,
        "latency_ms": result.latency_ms,
        "from_cache": result.from_cache,
        "from_showcase": result.from_showcase,
        "sources_used": result.sources_used,
        "confidence": result.confidence,
        "graph_available": result.graph_available,
    }
