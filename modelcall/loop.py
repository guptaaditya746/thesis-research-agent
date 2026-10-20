"""One event loop for every one-off model call."""
from __future__ import annotations

import asyncio
import threading
from collections.abc import Coroutine
from typing import Any, TypeVar

R = TypeVar("R")

# pydantic-ai's OpenAI models share one cached httpx client per process, and a pooled keep-alive connection
# belongs to the loop that opened it: a second `asyncio.run` in the same process reuses a connection of the
# first, closed loop and fails after the server answered ("Event loop is closed"). Sync callers therefore
# run every call on this one loop in a daemon thread.

_loop: asyncio.AbstractEventLoop | None = None
_loop_lock = threading.Lock()


def model_loop() -> asyncio.AbstractEventLoop:
    """The loop model calls run on: started at first use in a daemon thread, never closed."""
    global _loop
    with _loop_lock:
        if _loop is None:
            _loop = asyncio.new_event_loop()
            threading.Thread(target=_loop.run_forever, name="gold-model-loop", daemon=True).start()
        return _loop


def _running() -> asyncio.AbstractEventLoop | None:
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        return None


def run_sync(coro: Coroutine[Any, Any, R]) -> R:
    """Run a coroutine on the model loop and wait for it: from sync code in any thread, or from inside
    another running loop (which then waits too; async code should await `on_model_loop` instead)."""
    loop = model_loop()
    if _running() is loop:
        coro.close()
        raise RuntimeError("a sync model call on the model loop would wait for itself; await the async call")
    return asyncio.run_coroutine_threadsafe(coro, loop).result()


async def on_model_loop(coro: Coroutine[Any, Any, R]) -> R:
    """Await a coroutine on the model loop from any loop (directly when already on it)."""
    loop = model_loop()
    if _running() is loop:
        return await coro
    return await asyncio.wrap_future(asyncio.run_coroutine_threadsafe(coro, loop))
