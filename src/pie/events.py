from __future__ import annotations

import asyncio
import fnmatch
import inspect
import json
import logging
import threading
import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

_LOG = logging.getLogger(__name__)
Handler = Callable[["Event"], Any]


@dataclass(frozen=True, slots=True)
class Event:
    topic: str
    payload: Mapping[str, Any]
    source: str
    ts: float
    id: str
    correlation_id: str | None = None


@dataclass(slots=True)
class _Subscriber:
    pattern: str
    handler: Handler
    name: str
    queue: asyncio.Queue[Event]
    task: asyncio.Task[None] | None = None
    closed: bool = False
    drops: int = 0


class EventBus:
    """Thread-safe, non-blocking event publication with isolated FIFO subscribers."""

    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self.loop = loop
        self._lock = threading.Lock()
        self._subscribers: list[_Subscriber] = []
        self._last_warning = 0.0
        self._warning_lock = threading.Lock()

    def publish(
        self,
        topic: str,
        payload: Mapping[str, Any] | None = None,
        *,
        source: str,
        correlation_id: str | None = None,
    ) -> Event:
        data: Mapping[str, Any] = {} if payload is None else dict(payload)
        if self.loop.get_debug():
            try:
                json.dumps(data)
            except (TypeError, ValueError) as exc:
                raise ValueError("event payload must be JSON-serializable in debug mode") from exc
        event = Event(topic, data, source, time.time(), uuid.uuid4().hex, correlation_id)
        if self.loop.is_closed():
            return event
        try:
            self.loop.call_soon_threadsafe(self._dispatch, event)
        except RuntimeError:
            return event
        return event

    def _dispatch(self, event: Event) -> None:
        with self._lock:
            subscribers = tuple(self._subscribers)
        for subscriber in subscribers:
            if subscriber.closed or not fnmatch.fnmatchcase(event.topic, subscriber.pattern):
                continue
            if subscriber.queue.full():
                try:
                    subscriber.queue.get_nowait()
                    subscriber.queue.task_done()
                except asyncio.QueueEmpty:
                    pass
                subscriber.drops += 1
                self._warn_overflow(event.topic, subscriber)
            try:
                subscriber.queue.put_nowait(event)
            except asyncio.QueueFull:
                subscriber.drops += 1

    def _warn_overflow(self, topic: str, subscriber: _Subscriber) -> None:
        if topic.startswith("system."):
            return
        now = time.monotonic()
        with self._warning_lock:
            if now - self._last_warning < 5.0:
                return
            self._last_warning = now
        warning = Event(
            "system.warning",
            {"where": "event_bus", "message": f"dropped oldest event for {subscriber.name}"},
            "event_bus", time.time(), uuid.uuid4().hex,
        )
        if not self.loop.is_closed():
            self.loop.call_soon(self._dispatch, warning)

    def subscribe(self, pattern: str, handler: Handler, *, name: str) -> Callable[[], None]:
        subscriber = _Subscriber(pattern, handler, name, asyncio.Queue(maxsize=1000))
        with self._lock:
            self._subscribers.append(subscriber)
        if not self.loop.is_closed():
            try:
                self.loop.call_soon_threadsafe(self._start_subscriber, subscriber)
            except RuntimeError:
                subscriber.closed = True

        def unsubscribe() -> None:
            with self._lock:
                if subscriber.closed:
                    return
                subscriber.closed = True
                if subscriber in self._subscribers:
                    self._subscribers.remove(subscriber)
            if not self.loop.is_closed():
                try:
                    self.loop.call_soon_threadsafe(self._cancel_subscriber, subscriber)
                except RuntimeError:
                    pass

        return unsubscribe

    def _start_subscriber(self, subscriber: _Subscriber) -> None:
        if not subscriber.closed and subscriber.task is None:
            subscriber.task = self.loop.create_task(self._run_subscriber(subscriber))

    def _cancel_subscriber(self, subscriber: _Subscriber) -> None:
        if subscriber.task is not None:
            subscriber.task.cancel()

    async def _run_subscriber(self, subscriber: _Subscriber) -> None:
        while not subscriber.closed:
            event = await subscriber.queue.get()
            try:
                if inspect.iscoroutinefunction(subscriber.handler):
                    await subscriber.handler(event)
                else:
                    result = await self.loop.run_in_executor(None, subscriber.handler, event)
                    if inspect.isawaitable(result):
                        await result
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                _LOG.exception("event handler %s failed for topic %s", subscriber.name, event.topic)
                self.publish(
                    "system.error",
                    {"where": f"bus:{subscriber.name}", "error": type(exc).__name__, "detail": str(exc)},
                    source="event_bus",
                )
            finally:
                subscriber.queue.task_done()

    async def wait_for(
        self,
        pattern: str,
        *,
        timeout: float,
        predicate: Callable[[Event], bool] | None = None,
    ) -> Event:
        future: asyncio.Future[Event] = self.loop.create_future()

        def receive(event: Event) -> None:
            if not future.done() and (predicate is None or predicate(event)):
                self.loop.call_soon_threadsafe(_resolve, future, event)

        def _resolve(target: asyncio.Future[Event], event: Event) -> None:
            if not target.done():
                target.set_result(event)

        unsubscribe = self.subscribe(pattern, receive, name="wait_for")
        try:
            return await asyncio.wait_for(future, timeout)
        finally:
            unsubscribe()
