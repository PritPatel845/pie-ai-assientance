from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from pie.core.daemon import Daemon
from pie.events import Event


class GestureBindingsModule:
    """Translate discrete rising-edge gestures into registered tool calls."""

    name = "gesture-bindings"

    def __init__(self, *, clock: Callable[[], float] = time.monotonic) -> None:
        self.clock = clock
        self._unsubscribe: Callable[[], None] | None = None
        self._last: dict[str, float] = {}
        self._armed = False
        self.daemon: Daemon | None = None

    def start(self, daemon: Daemon) -> None:
        self.daemon = daemon
        if daemon.bus is None or not daemon.config.gesture.bindings_via_tools:
            return
        self._unsubscribe = daemon.bus.subscribe(
            "input.gesture.*", self._on_gesture_event, name=self.name
        )

    async def _on_gesture_event(self, event: Event) -> None:
        if event.topic == "input.gesture.state":
            self._armed = bool(event.payload.get("armed", False))
            return
        if event.topic != "input.gesture.event" or not self._armed or self.daemon is None:
            return
        name = event.payload.get("name")
        if not isinstance(name, str):
            return
        tool_name = self.daemon.config.gesture.bindings.get(name)
        if not isinstance(tool_name, str) or not tool_name:
            return
        now = self.clock()
        if now - self._last.get(name, float("-inf")) < 1.0:
            return
        self._last[name] = now
        registry: Any = getattr(self.daemon, "tool_registry", None)
        if registry is None:
            return
        await registry.execute(
            tool_name,
            {},
            source="gesture",
            correlation_id=event.correlation_id or event.id,
        )

    def stop(self) -> None:
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None
        self._last.clear()
        self._armed = False
        self.daemon = None


__all__ = ["GestureBindingsModule"]
