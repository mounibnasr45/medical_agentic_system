"""Request-scoped trace event bus.

The pipeline streams its own progress rather than relying on framework callbacks.
A sink is bound to a `contextvars.ContextVar` for the duration of one request, and
any code on that context - including tools invoked deep inside a CrewAI run - can
publish to it without being passed a handle.

CrewAI executes crews synchronously, so `crew.kickoff()` runs in a worker thread.
`contextvars` do not cross `run_in_executor` automatically, so callers must copy
the context explicitly (see `emit_from_thread` usage in api/server.py).

When no sink is bound, publishing is a no-op. That keeps the tools usable from
tests, scripts and the non-streaming endpoint with no special casing.
"""

from __future__ import annotations

import asyncio
import contextvars
import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)


class EventType(StrEnum):
    """Every event the frontend knows how to render.

    Kept in sync with frontend/src/types/events.ts - changing one means changing both.
    """

    RUN_STARTED = "run_started"
    ROUTER_COMPLETED = "router_completed"
    REJECTED = "rejected"
    STAGE_STARTED = "stage_started"
    STAGE_COMPLETED = "stage_completed"
    TOOL_STARTED = "tool_started"
    TOOL_COMPLETED = "tool_completed"
    COT_STEP = "cot_step"
    ANSWER = "answer"
    RUN_COMPLETED = "run_completed"
    ERROR = "error"


@dataclass
class TraceEvent:
    type: EventType
    payload: dict[str, Any] = field(default_factory=dict)
    ts: float = field(default_factory=time.time)
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    def to_sse(self) -> str:
        """Serialise as a Server-Sent Event frame."""
        body = asdict(self)
        body["type"] = self.type.value
        return f"event: {self.type.value}\ndata: {json.dumps(body, default=str)}\n\n"


class EventSink:
    """An async queue of trace events for a single request."""

    _SENTINEL = object()

    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self._queue: asyncio.Queue = asyncio.Queue()
        self._loop = loop
        self._closed = False

    def emit(self, event_type: EventType, **payload: Any) -> None:
        """Publish an event. Safe to call from any thread.

        Never raises: a broken trace must not take down the query it is describing.
        """
        if self._closed:
            return
        event = TraceEvent(type=event_type, payload=payload)
        try:
            if self._loop.is_closed():
                return
            self._loop.call_soon_threadsafe(self._queue.put_nowait, event)
        except RuntimeError:
            # Loop shut down mid-flight; drop the event rather than fail the request.
            logger.debug("Dropped trace event %s: loop unavailable", event_type)

    def close(self) -> None:
        self._closed = True
        try:
            self._loop.call_soon_threadsafe(self._queue.put_nowait, self._SENTINEL)
        except RuntimeError:
            pass

    async def drain(self):
        """Yield events until the sink is closed."""
        while True:
            item = await self._queue.get()
            if item is self._SENTINEL:
                return
            yield item


_current_sink: contextvars.ContextVar[EventSink | None] = contextvars.ContextVar(
    "medical_agent_event_sink", default=None
)


def bind_sink(sink: EventSink) -> contextvars.Token:
    return _current_sink.set(sink)


def unbind_sink(token: contextvars.Token) -> None:
    _current_sink.reset(token)


def emit(event_type: EventType, **payload: Any) -> None:
    """Publish to the sink bound to the current context, if any."""
    sink = _current_sink.get()
    if sink is not None:
        sink.emit(event_type, **payload)


class stage:
    """Context manager emitting STAGE_STARTED / STAGE_COMPLETED around a block.

    Records elapsed milliseconds so the UI can show real per-stage timings.
    """

    def __init__(self, name: str, **meta: Any) -> None:
        self.name = name
        self.meta = meta
        self._start = 0.0

    def __enter__(self) -> stage:
        self._start = time.perf_counter()
        emit(EventType.STAGE_STARTED, stage=self.name, **self.meta)
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        elapsed_ms = int((time.perf_counter() - self._start) * 1000)
        emit(
            EventType.STAGE_COMPLETED,
            stage=self.name,
            elapsed_ms=elapsed_ms,
            ok=exc_type is None,
            error=str(exc) if exc else None,
        )
        return False
