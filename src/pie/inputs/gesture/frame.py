from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal

from pie.inputs.gesture.features import (
    Landmark,
    classify_desktop,
    is_fist,
    is_four_finger,
    is_open_palm,
    is_pinch,
    is_three_finger,
    is_thumb_down,
    is_thumb_up,
    is_two_finger,
)
from pie.inputs.gesture.game import GAME_PROFILES, game_gesture


@dataclass(frozen=True, slots=True)
class MoveCursor:
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class DoubleClick:
    pass


@dataclass(frozen=True, slots=True)
class Mute:
    pass


@dataclass(frozen=True, slots=True)
class PlayMedia:
    pass


@dataclass(frozen=True, slots=True)
class StopMedia:
    pass


@dataclass(frozen=True, slots=True)
class RunVoiceCommand:
    pass


@dataclass(frozen=True, slots=True)
class Scroll:
    amount: int


@dataclass(frozen=True, slots=True)
class SetVolume:
    value: int


@dataclass(frozen=True, slots=True)
class KeyAction:
    name: str
    pressed: bool


@dataclass(frozen=True, slots=True)
class Tap:
    name: str


@dataclass(frozen=True, slots=True)
class MouseClick:
    pass


Action = (
    MoveCursor
    | DoubleClick
    | Mute
    | PlayMedia
    | StopMedia
    | RunVoiceCommand
    | Scroll
    | SetVolume
    | KeyAction
    | Tap
    | MouseClick
)


@dataclass(frozen=True, slots=True)
class FrameResult:
    gesture: str
    depth: float | None
    volume: int | None
    armed: bool
    actions: list[Action]


class FrameProcessor:
    """Pure gesture state machine. All OS effects are returned as typed actions."""

    def __init__(
        self, *, arm_hold_seconds: float = 2.0, steer_sensitivity: float = 0.004, clock: Callable[[], float] | None = None
    ) -> None:
        import time

        self.arm_hold_seconds = arm_hold_seconds
        self.steer_sensitivity = steer_sensitivity
        self._clock = clock or time.monotonic
        self.mode: Literal["desktop", "game"] = "desktop"
        self.profile = "asphalt"
        self.armed = False
        self._palm_since: float | None = None
        self._previous: set[str] = set()
        self._last_pinch = float("-inf")
        self._previous_x: float | None = None
        self._last_volume: int | None = None
        self._last_volume_at = float("-inf")
        self._steering_center: float | None = None
        self._held: set[str] = set()
        self._previous_game = "GAME READY"
        self._previous_index: Landmark | None = None

    def set_mode(
        self, mode: Literal["desktop", "game"], profile: str | None = None
    ) -> list[Action]:
        if mode not in ("desktop", "game"):
            raise ValueError("mode must be desktop or game")
        if profile is not None and profile not in GAME_PROFILES:
            raise ValueError(f"unknown game profile: {profile}")
        actions: list[Action] = self._release_keys()
        self.mode = mode
        if profile is not None:
            self.profile = profile
        self._disarm()
        self._previous.clear()
        self._previous_index = None
        return actions

    def reset(self) -> list[Action]:
        actions = self._release_keys()
        self._disarm()
        self._previous.clear()
        self._previous_x = None
        self._previous_index = None
        return actions

    def _disarm(self) -> None:
        self.armed = False
        self._palm_since = None
        self._steering_center = None

    def _release_keys(self) -> list[Action]:
        actions = [KeyAction(name, False) for name in sorted(self._held)]
        self._held.clear()
        return actions

    def _key(self, name: str, pressed: bool, actions: list[Action]) -> None:
        if pressed and name not in self._held:
            self._held.add(name)
            actions.append(KeyAction(name, True))
        elif not pressed and name in self._held:
            self._held.remove(name)
            actions.append(KeyAction(name, False))

    def process(self, hands: Sequence[Sequence[Landmark]], now: float | None = None) -> FrameResult:
        timestamp = self._clock() if now is None else now
        actions: list[Action] = []
        if not hands:
            actions.extend(self._release_keys())
            self._disarm()
            self._previous.clear()
            self._previous_x = None
            self._previous_index = None
            self._last_volume = None
            return FrameResult("NO HAND", None, None, False, actions)

        hand = hands[0]
        gesture = classify_desktop(hand)
        depth = float(hand[9].z)
        volume = int(max(0, min(100, 72 - depth * 180)))

        if not self.armed:
            if is_open_palm(hand):
                if self._palm_since is None:
                    self._palm_since = timestamp
                elif timestamp - self._palm_since >= self.arm_hold_seconds:
                    self.armed = True
                    self._steering_center = float(hand[9].x)
            else:
                self._palm_since = None

        if self.armed and self.mode == "desktop":
            actions.append(MoveCursor(float(hand[8].x), float(hand[8].y)))
            pinch = is_pinch(hand)
            if pinch and "pinch" not in self._previous and timestamp - self._last_pinch >= 0.7:
                actions.append(DoubleClick())
                self._last_pinch = timestamp
            if is_three_finger(hand) and "three" not in self._previous:
                actions.append(DoubleClick())
            if is_open_palm(hand) and hand[9].z < -0.12 and "mute" not in self._previous:
                actions.append(Mute())
            if is_fist(hand) and "fist" not in self._previous:
                actions.append(RunVoiceCommand())
            if is_thumb_up(hand) and "thumb_up" not in self._previous:
                actions.append(PlayMedia())
            if is_thumb_down(hand) and "thumb_down" not in self._previous:
                actions.append(StopMedia())
            if is_two_finger(hand):
                if self._previous_x is not None and abs(hand[8].x - self._previous_x) > 0.08:
                    actions.append(Scroll(-5 if hand[8].x > self._previous_x else 5))
                self._previous_x = float(hand[8].x)
            else:
                self._previous_x = None
            if (
                self._last_volume is None
                or abs(volume - self._last_volume) >= 2
                or timestamp - self._last_volume_at >= 0.2
            ):
                actions.append(SetVolume(volume))
                self._last_volume = volume
                self._last_volume_at = timestamp
        elif self.armed and self.mode == "game":
            profile = GAME_PROFILES[self.profile]
            label = game_gesture(hand, self._previous_index, hand[8])
            rising = label != self._previous_game
            style = profile["style"]
            if style == "racing":
                drifting = is_two_finger(hand)
                self._key(
                    "left",
                    is_three_finger(hand)
                    or (
                        drifting
                        and self._steering_center is not None
                        and hand[9].x - self._steering_center < -self.steer_sensitivity
                    ),
                    actions,
                )
                self._key(
                    "right",
                    is_four_finger(hand)
                    or (
                        drifting
                        and self._steering_center is not None
                        and hand[9].x - self._steering_center > self.steer_sensitivity
                    ),
                    actions,
                )
                self._key(
                    "accelerate",
                    (is_three_finger(hand) or is_four_finger(hand)) and not drifting,
                    actions,
                )
                self._key("brake", is_fist(hand) or drifting, actions)
                if is_pinch(hand) and rising:
                    actions.append(Tap("nitro"))
            elif style == "runner":
                if rising and label == "THREE FINGER / LEFT":
                    actions.append(Tap("left"))
                elif rising and label == "FOUR FINGER / RIGHT":
                    actions.append(Tap("right"))
                elif rising and label == "THUMB UP / JUMP":
                    actions.append(Tap("jump"))
                if is_fist(hand):
                    self._key("slide", True, actions)
                else:
                    self._key("slide", False, actions)
            elif style == "fps":
                self._key("left", is_three_finger(hand), actions)
                self._key("right", is_four_finger(hand), actions)
                dx = (hand[8].x - self._previous_index.x) if self._previous_index else 0.0
                self._key("forward", is_open_palm(hand) and abs(dx) <= 0.035, actions)
                self._key("back", is_fist(hand), actions)
                if is_pinch(hand) and rising:
                    actions.append(MouseClick())
                if is_thumb_up(hand) and rising:
                    actions.append(Tap("jump"))
            self._previous_game = label

        self._previous_index = hand[8]
        current = set()
        if is_pinch(hand):
            current.add("pinch")
        if is_three_finger(hand):
            current.add("three")
        if is_open_palm(hand) and hand[9].z < -0.12:
            current.add("mute")
        if is_fist(hand):
            current.add("fist")
        if is_thumb_up(hand):
            current.add("thumb_up")
        if is_thumb_down(hand):
            current.add("thumb_down")
        self._previous = current
        return FrameResult(gesture, depth, volume, self.armed, actions)
