from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from pie.inputs.gesture.features import (
    is_fist,
    is_four_finger,
    is_open_palm,
    is_pinch,
    is_three_finger,
    is_thumb_up,
    is_two_finger,
)


class Point(Protocol):
    x: float
    y: float


GAME_PROFILES: dict[str, dict[str, str]] = {
    "asphalt": {"style": "racing", "left": "left", "right": "right", "accelerate": "up",
                "brake": "down", "nitro": "space"},
    "temple-run": {"style": "runner", "left": "left", "right": "right", "jump": "up",
                   "slide": "down"},
    "counter-strike": {"style": "fps", "left": "a", "right": "d", "forward": "w",
                       "back": "s", "jump": "space"},
}
PROFILE_KEYS = {"1": "asphalt", "2": "temple-run", "3": "counter-strike"}
MAC_KEY_CODES = {"a": 0, "s": 1, "d": 2, "w": 13, "space": 49,
                 "left": 123, "right": 124, "down": 125, "up": 126}


def game_gesture(hand: Sequence[Point], previous_index: Point | None, index: Point) -> str:
    if is_pinch(hand):
        return "PINCH / ACTION"
    if is_thumb_up(hand):
        return "THUMB UP / JUMP"
    if is_two_finger(hand):
        return "TWO-FINGER / DRIFT"
    if is_fist(hand):
        return "FIST / BRAKE"
    if is_three_finger(hand):
        return "THREE FINGER / LEFT"
    if is_four_finger(hand):
        return "FOUR FINGER / RIGHT"
    if is_open_palm(hand) and previous_index is not None:
        dx, dy = index.x - previous_index.x, index.y - previous_index.y
        if abs(dx) > 0.05:
            return "SWIPE RIGHT" if dx > 0 else "SWIPE LEFT"
        if dy < -0.055:
            return "PALM UP / JUMP"
        if dy > 0.055:
            return "PALM DOWN / SLIDE"
    return "GAME READY"


class KeyPoster(Protocol):
    def key_event(self, code: int, pressed: bool) -> None: ...


class GameController:
    def __init__(self, profile: str, poster: KeyPoster) -> None:
        if profile not in GAME_PROFILES:
            raise ValueError(f"Unknown game profile: {profile}")
        self.profile, self.poster = profile, poster
        self._held: set[str] = set()

    @property
    def held_keys(self) -> frozenset[str]:
        return frozenset(self._held)

    def set_key(self, action: str, pressed: bool) -> None:
        key = GAME_PROFILES[self.profile].get(action)
        if key is None or (key in self._held) == pressed:
            return
        self.poster.key_event(MAC_KEY_CODES[key], pressed)
        if pressed:
            self._held.add(key)
        else:
            self._held.discard(key)

    def tap(self, action: str) -> None:
        self.set_key(action, True)
        self.set_key(action, False)

    def release_all(self) -> None:
        for key in tuple(self._held):
            self.poster.key_event(MAC_KEY_CODES[key], False)
        self._held.clear()
