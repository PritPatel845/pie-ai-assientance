from __future__ import annotations

import asyncio
import fnmatch
import json
import logging
import threading
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

_LOG = logging.getLogger(__name__)
Handler = Callable[["Event"], Any | Awaitable[Any]]


@dataclass(frozen=True, slots=True)
class Event:
    topic: str
    payload: dict[str, Any]
    timestamp: float
    event_id: str


@dataclass(slots=True)
class _Subscriber:
    pattern: str
    handler: Handler
    queue: asyncio.Queue[Event]
    task: asyncio.Task[None] | None = None
    closed: bool = False


class EventBus:
    """Thread-safe publisher with isolated, FIFO subscriber queues."""

    def __init__(self, loop: asyncio.AbstractEventLoop, *, queue_size: int = 1000,
                 debug_serialization: bool = False) -> None:
        if queue_size < 1:
            raise ValueError("queue_size must be positive")
        self._loop = loop
        self._queue_size = queue_size
        self._debug_serialization = debug_serialization
        self._lock = threading.RLock()
        self._subscribers: dict[str, _Subscriber] = {}
        self._closed = False
        self._last_overflow_warning = 0.0

    def subscribe(self, pattern: str, handler: Handler) -> Callable[[], None]:
        if not pattern:
            raise ValueError("topic pattern cannot be empty")
        token = uuid.uuid4().hex

        def add() -> None:
            with self._lock:
                if self._closed:
                    return
                sub = _Subscriber(pattern, handler, asyncio.Queue(self._queue_size))
                self._subscribers[token] = sub
                sub.task = self._loop.create_task(self._dispatch(token, sub))

        if threading.current_thread() is threading.main_thread() and self._loop.is_running():
            add()
        else:
            self._loop.call_soon_threadsafe(add)

        def unsubscribe() -> None:
            def remove() -> None:
                with self._lock:
                    sub = self._subscribers.pop(token, None)
                    if sub is None:
                        return
                    sub.closed = True
                    if sub.task:
                        sub.task.cancel()
            if self._loop.is_closed():
                return
            self._loop.call_soon_threadsafe(remove)
        return unsubscribe

    def publish(self, topic: str, payload: dict[str, Any] | None = None) -> None:
        if self._closed or self._loop.is_closed():
            return
        data = dict(payload or {})
        if self._debug_serialization:
            json.dumps(data, allow_nan=False)
        event = Event(topic, data, time.time(), uuid.uuid4().hex)

        def deliver() -> None:
            with self._lock:
                targets = [s for s in self._subscribers.values()
                           if not s.closed and fnmatch.fnmatchcase(topic, s.pattern)]
            for sub in targets:
                if sub.queue.full():
                    try:
                        sub.queue.get_nowait()
                        sub.queue.task_done()
                    except asyncio.QueueEmpty:
                        pass
                    now = time.monotonic()
                    if not topic.startswith("system.") and now - self._last_overflow_warning >= 5:
                        self._last_overflow_warning = now
                        _LOG.warning("Event subscriber queue overflow; oldest event dropped")
                try:
                    sub.queue.put_nowait(event)
                except asyncio.QueueFull:
                    _LOG.warning("Event dropped because subscriber queue remained full")

        try:
            self._loop.call_soon_threadsafe(deliver)
        except RuntimeError:
            # The loop may close between the is_closed check and scheduling.
            return

    async def _dispatch(self, token: str, sub: _Subscriber) -> None:
        while not sub.closed:
            event = await sub.queue.get()
            try:
                if asyncio.iscoroutinefunction(sub.handler):
                    await sub.handler(event)
                else:
                    result = await self._loop.run_in_executor(None, sub.handler, event)
                    if asyncio.iscoroutine(result):
                        await result
            except asyncio.CancelledError:
                raise
            except Exception:
                _LOG.exception("Event handler failed for topic %s", event.topic)
                if not event.topic.startswith("system."):
                    self.publish("system.error", {"source_topic": event.topic})
            finally:
                sub.queue.task_done()

    async def close(self, *, timeout: float = 3.0) -> None:
        def shutdown() -> list[asyncio.Task[None]]:
            with self._lock:
                self._closed = True
                tasks = []
                for sub in self._subscribers.values():
                    sub.closed = True
                    if sub.task:
                        sub.task.cancel()
                        tasks.append(sub.task)
                self._subscribers.clear()
                return tasks
        tasks = shutdown()
        if tasks:
            try:
                await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout)
            except asyncio.TimeoutError:
                _LOG.warning("Timed out while closing event subscribers")
