from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Literal


class StopFlag:
    """Small thread-safe stop signal shared by the daemon and worker threads."""

    def __init__(self) -> None:
        self._event = threading.Event()

    def set(self) -> None:
        self._event.set()

    def is_set(self) -> bool:
        return self._event.is_set()

    def wait(self, timeout: float | None = None) -> bool:
        return self._event.wait(timeout)


@dataclass(frozen=True, slots=True)
class StateSnapshot:
    mode: Literal["desktop", "game", "idle"]
    game_profile: str | None
    armed: bool
    last_gesture: str | None


class RuntimeState:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._mode: Literal["desktop", "game", "idle"] = "desktop"
        self._game_profile: str | None = "asphalt"
        self._armed = False
        self._last_gesture: str | None = None

    def update(
        self,
        *,
        mode: Literal["desktop", "game", "idle"] | None = None,
        game_profile: str | None = None,
        armed: bool | None = None,
        last_gesture: str | None = None,
    ) -> None:
        with self._lock:
            if mode is not None:
                self._mode = mode
            if game_profile is not None:
                self._game_profile = game_profile
            if armed is not None:
                self._armed = armed
            if last_gesture is not None:
                self._last_gesture = last_gesture

    def snapshot(self) -> StateSnapshot:
        with self._lock:
            return StateSnapshot(self._mode, self._game_profile, self._armed, self._last_gesture)
