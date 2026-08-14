"""A dedicated event loop for all graph work.

Neo4j's async driver binds its internal locks to the event loop that created the
connection pool. The application has more than one loop: the request loop, and a
fresh one per `asyncio.run()` inside tools that CrewAI invokes synchronously from
worker threads. Sharing one cached client across them fails with

    <AsyncRLock ...> is bound to a different event loop

and, because graph tools degrade rather than raise, that failure is invisible: the
agent quietly answers from web search instead.

So every graph coroutine runs on one long-lived loop in a background thread.
Callers submit work to it and wait, from either sync or async context.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Coroutine
from typing import Any, TypeVar

T = TypeVar("T")

DEFAULT_TIMEOUT = 60.0

_loop: asyncio.AbstractEventLoop | None = None
_thread: threading.Thread | None = None
_lock = threading.Lock()


def _ensure_loop() -> asyncio.AbstractEventLoop:
    global _loop, _thread
    with _lock:
        if _loop is None or _loop.is_closed():
            _loop = asyncio.new_event_loop()
            _thread = threading.Thread(
                target=_loop.run_forever,
                name="graph-loop",
                daemon=True,
            )
            _thread.start()
        return _loop


def _submit(coro: Coroutine[Any, Any, T]):
    return asyncio.run_coroutine_threadsafe(coro, _ensure_loop())


def run_sync(coro: Coroutine[Any, Any, T], timeout: float = DEFAULT_TIMEOUT) -> T:
    """Run a graph coroutine from synchronous code and wait for the result."""
    return _submit(coro).result(timeout)


async def run_async(coro: Coroutine[Any, Any, T], timeout: float = DEFAULT_TIMEOUT) -> T:
    """Run a graph coroutine from another event loop without blocking it."""
    return await asyncio.wait_for(asyncio.wrap_future(_submit(coro)), timeout=timeout)


def shutdown() -> None:
    """Stop the loop. Used at application shutdown."""
    global _loop, _thread
    with _lock:
        if _loop is not None and not _loop.is_closed():
            _loop.call_soon_threadsafe(_loop.stop)
            if _thread is not None:
                _thread.join(timeout=5)
            _loop.close()
        _loop, _thread = None, None
