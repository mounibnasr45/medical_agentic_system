"""The trace event bus that drives the live pipeline view."""

import asyncio
import json

import pytest

from medical_agent.utils.events import (
    EventSink,
    EventType,
    TraceEvent,
    bind_sink,
    emit,
    stage,
    unbind_sink,
)


def test_serialises_as_a_valid_sse_frame():
    frame = TraceEvent(type=EventType.TOOL_STARTED, payload={"tool": "graph_db"}).to_sse()

    assert frame.startswith("event: tool_started\n")
    assert frame.endswith("\n\n")  # frame terminator

    data = json.loads(frame.split("data: ", 1)[1].strip())
    assert data["type"] == "tool_started"
    assert data["payload"]["tool"] == "graph_db"


def test_emitting_without_a_sink_is_a_no_op():
    """Tools are used by scripts and the blocking endpoint, where no sink exists."""
    emit(EventType.TOOL_STARTED, tool="graph_db")


@pytest.mark.asyncio
async def test_events_reach_the_bound_sink_in_order():
    sink = EventSink(asyncio.get_running_loop())
    token = bind_sink(sink)
    try:
        emit(EventType.RUN_STARTED, query="q")
        emit(EventType.ANSWER, text="a")
    finally:
        unbind_sink(token)
    sink.close()

    received = [event async for event in sink.drain()]

    assert [e.type for e in received] == [EventType.RUN_STARTED, EventType.ANSWER]


@pytest.mark.asyncio
async def test_stage_records_success_and_elapsed_time():
    sink = EventSink(asyncio.get_running_loop())
    token = bind_sink(sink)
    try:
        with stage("router", detail="x"):
            pass
    finally:
        unbind_sink(token)
    sink.close()

    received = [event async for event in sink.drain()]

    assert [e.type for e in received] == [
        EventType.STAGE_STARTED,
        EventType.STAGE_COMPLETED,
    ]
    assert received[1].payload["ok"] is True
    assert received[1].payload["elapsed_ms"] >= 0


@pytest.mark.asyncio
async def test_stage_records_failure_without_swallowing_the_error():
    sink = EventSink(asyncio.get_running_loop())
    token = bind_sink(sink)
    try:
        with pytest.raises(ValueError):
            with stage("crew"):
                raise ValueError("boom")
    finally:
        unbind_sink(token)
    sink.close()

    completed = [e async for e in sink.drain()][-1]

    assert completed.payload["ok"] is False
    assert "boom" in completed.payload["error"]


@pytest.mark.asyncio
async def test_a_closed_sink_ignores_further_events():
    sink = EventSink(asyncio.get_running_loop())
    sink.close()
    sink.emit(EventType.ANSWER, text="late")

    assert [event async for event in sink.drain()] == []


@pytest.mark.asyncio
async def test_events_emitted_from_a_worker_thread_arrive():
    """CrewAI runs synchronously in an executor; tool events originate off-loop."""
    import contextvars

    loop = asyncio.get_running_loop()
    sink = EventSink(loop)
    token = bind_sink(sink)

    def work():
        emit(EventType.TOOL_STARTED, tool="graph_db")

    try:
        ctx = contextvars.copy_context()
        await loop.run_in_executor(None, lambda: ctx.run(work))
    finally:
        unbind_sink(token)
    sink.close()

    received = [event async for event in sink.drain()]

    assert [e.type for e in received] == [EventType.TOOL_STARTED]
