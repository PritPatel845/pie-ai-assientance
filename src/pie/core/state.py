from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any


class StopFlag:
    """Thread-safe, idempotent stop signal shared by runtime modules."""

    def __init__(self) -> None:
        self._event = threading.Event()

    def request(self) -> None:
        self._event.set()

    def is_set(self) -> bool:
        return self._event.is_set()

    def wait(self, timeout: float | None = None) -> bool:
        return self._event.wait(timeout)


@dataclass(frozen=True, slots=True)
class StateSnapshot:
    mode: str
    running: bool
    values: tuple[tuple[str, Any], ...]


class RuntimeState:
    """Small lock-protected state store; readers receive immutable snapshots."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._mode = "idle"
        self._running = False
        self._values: dict[str, Any] = {}

    def update(self, *, mode: str | None = None, running: bool | None = None,
               values: dict[str, Any] | None = None) -> None:
        with self._lock:
            if mode is not None:
                self._mode = mode
            if running is not None:
                self._running = running
            if values:
                self._values.update(values)

    def snapshot(self) -> StateSnapshot:
        with self._lock:
            return StateSnapshot(self._mode, self._running,
                                 tuple(sorted(self._values.items())))
