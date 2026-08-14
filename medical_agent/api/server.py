"""HTTP API.

Two ways to ask the same question:

    POST /ask         blocking, returns the answer and its metadata
    POST /ask/stream  Server-Sent Events, streaming the pipeline trace live

Both call `pipeline.run_query`. The streaming endpoint binds an event sink for the
duration of the request; every component publishes to it, and the generator relays
those events to the client as they arrive.

Queries are capped per IP per day because this is an unauthenticated public demo in
front of a paid model. Pre-computed showcase questions are exempt, so a visitor can
explore the system without spending their allowance.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from medical_agent import pipeline
from medical_agent.config import Config
from medical_agent.graph.client import get_gateway
from medical_agent.utils import showcase
from medical_agent.utils.events import EventSink, EventType, bind_sink, unbind_sink
from medical_agent.utils.memory_manager import MemoryManager
from medical_agent.utils.rate_limit import client_key, get_limiter

logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)

# Third-party loggers that report routine work at INFO. Left alone they emit
# dozens of lines per connect - Neo4j announces every "index already exists" -
# which buries the one line that matters when something actually breaks.
for _noisy in ("neo4j.notifications", "neo4j", "httpx", "httpcore", "LiteLLM", "litellm"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

MAX_QUERY_CHARS = 1000


@asynccontextmanager
async def lifespan(app: FastAPI):
    missing = Config.missing_required()
    if missing:
        logger.warning("Missing required settings: %s", ", ".join(missing))
    logger.info(
        "Starting: graph=%s origins=%s daily_limit=%d",
        "configured" if Config.graph_configured() else "disabled",
        Config.ALLOWED_ORIGINS,
        Config.DAILY_QUERY_LIMIT,
    )
    yield

    # The client belongs to the graph loop, so it must be closed there too.
    from medical_agent.graph import loop as graph_loop

    try:
        await graph_loop.run_async(get_gateway().close(), timeout=10)
    except Exception as exc:
        logger.debug("Graph shutdown: %s", exc)
    graph_loop.shutdown()


app = FastAPI(
    title="Medical Agent API",
    description="Multi-agent clinical question answering over a temporal knowledge graph.",
    version="2.0.0",
    lifespan=lifespan,
)

# Locked to known origins. The previous wildcard allowed any site to spend this
# deployment's model quota from a visitor's browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=Config.ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
)


class QueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=MAX_QUERY_CHARS)
    session_id: str | None = None
    force_parallel: bool | None = None


def _caller(request: Request) -> str:
    return client_key(
        request.headers.get("x-forwarded-for"),
        request.client.host if request.client else None,
    )


def _enforce_quota(request: Request, query: str):
    """Consume one unit of the caller's daily allowance.

    Showcase questions are answered from disk and cost nothing, so they are
    checked but not charged.
    """
    limiter = get_limiter()
    key = _caller(request)

    if showcase.lookup(query):
        return limiter.peek(key)

    quota = limiter.consume(key)
    if not quota.allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "message": (
                    f"Daily demo limit of {quota.limit} queries reached. "
                    "The showcase examples remain available and do not count "
                    "towards the limit."
                ),
                "quota": quota.as_dict(),
            },
        )
    return quota


@app.get("/")
def root():
    return {
        "service": "Medical Agent API",
        "docs": "/docs",
        "health": "/health",
        "endpoints": ["/ask", "/ask/stream", "/showcase", "/quota"],
    }


@app.get("/health")
async def health():
    """Liveness and dependency status. Makes no model calls.

    Used by Render's health check and by the scheduled keep-alive ping, so it must
    stay cheap and must never fail because a dependency is down.
    """
    graph = await get_gateway().health()
    return {
        "status": "ok",
        "graph": graph,
        "llm_configured": bool(Config.GROQ_API_KEY),
        "embeddings_configured": bool(Config.GOOGLE_API_KEY),
        "daily_query_limit": Config.DAILY_QUERY_LIMIT,
    }


@app.get("/showcase")
def showcase_catalogue():
    """Example queries, flagged with whether each is pre-computed."""
    return {"examples": showcase.catalogue()}


@app.get("/quota")
def quota(request: Request):
    return get_limiter().peek(_caller(request)).as_dict()


@app.post("/ask")
async def ask(request: Request, body: QueryRequest):
    """Answer a question and return the result once complete."""
    quota = _enforce_quota(request, body.query)
    try:
        result = await pipeline.run_query(
            query=body.query,
            session_id=body.session_id,
            force_parallel=body.force_parallel,
        )
    except Exception as exc:
        logger.exception("Query failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    payload = result.as_dict()
    payload["quota"] = quota.as_dict()
    return payload


@app.post("/ask/stream")
async def ask_stream(request: Request, body: QueryRequest):
    """Answer a question, streaming the pipeline trace as Server-Sent Events."""
    quota = _enforce_quota(request, body.query)

    async def generate():
        loop = asyncio.get_running_loop()
        sink = EventSink(loop)
        token = bind_sink(sink)

        async def run():
            try:
                await pipeline.run_query(
                    query=body.query,
                    session_id=body.session_id,
                    force_parallel=body.force_parallel,
                )
            except Exception as exc:
                logger.exception("Streamed query failed")
                sink.emit(EventType.ERROR, message=str(exc))
            finally:
                sink.close()

        # Created inside the bound context, so the sink is visible to everything
        # the pipeline touches, including tools running in worker threads.
        task = asyncio.create_task(run())
        try:
            sink.emit(EventType.STAGE_STARTED, stage="quota", **quota.as_dict())
            async for event in sink.drain():
                if await request.is_disconnected():
                    break
                yield event.to_sse()
        finally:
            unbind_sink(token)
            if not task.done():
                task.cancel()

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # Render fronts the service with a buffering proxy; without this the
            # trace arrives all at once when the response closes.
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/sessions/{session_id}/history")
def session_history(session_id: str, limit: int = 20):
    memory = MemoryManager.get_session(session_id)
    return {
        "session_id": session_id,
        "history": memory.history(limit=limit),
        "stats": memory.stats(),
    }


@app.delete("/sessions/{session_id}")
def delete_session(session_id: str):
    if not MemoryManager.delete_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"deleted": session_id}


@app.post("/sessions/new")
def new_session():
    return {"session_id": MemoryManager.get_session().session_id}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=Config.PORT)
