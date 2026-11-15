"""FrameProcessor timing, arming, desktop actions, and game state
follow Phase 0S §3.3 (PDF pp. 18–19)."""

from dataclasses import dataclass

from pie.inputs.gesture.frame import (
    FrameProcessor,
    KeyAction,
    MoveCursor,
    SetVolume,
    Tap,
)


@dataclass
class P:
    x: float
    y: float
    z: float = 0.0


def hand(*, extended=(True, True, True, True), thumb_y=0.3, z=0.0, shift=0.0):
    points = [P(0.5 + shift, 0.7, z) for _ in range(21)]
    points[0] = P(0.5 + shift, 0.8, z)
    points[9] = P(0.5 + shift, 0.5, z)
    for (tip, pip), is_up in zip(((8, 6), (12, 10), (16, 14), (20, 18)), extended, strict=False):
        points[pip] = P(0.5 + shift, 0.6, z)
        points[tip] = P(0.5 + shift, 0.3 if is_up else 0.68, z)
    points[4] = P(0.35 + shift, thumb_y, z)
    points[8] = P(0.5 + shift, 0.3 if extended[0] else 0.68, z)
    return points


def test_open_palm_arms_only_after_hold() -> None:
    processor = FrameProcessor(arm_hold_seconds=2.0)
    palm = hand()
    assert not processor.process([palm], 0.0).armed
    assert not processor.process([palm], 1.9).armed
    assert processor.process([palm], 2.1).armed


def test_non_palm_resets_arm_timer() -> None:
    processor = FrameProcessor(arm_hold_seconds=2.0)
    palm, fist = hand(), hand(extended=(False, False, False, False))
    processor.process([palm], 0.0)
    processor.process([fist], 1.5)
    assert not processor.process([palm], 2.1).armed
    assert processor.process([palm], 4.2).armed


def test_armed_desktop_emits_cursor_and_volume() -> None:
    processor = FrameProcessor(arm_hold_seconds=0)
    palm = hand()
    processor.process([palm], 0)
    result = processor.process([palm], 0.1)
    assert result.armed
    assert any(isinstance(action, MoveCursor) for action in result.actions)
    assert any(isinstance(action, SetVolume) for action in result.actions)


def test_no_hand_disarms_and_releases_keys() -> None:
    processor = FrameProcessor()
    processor._held.add("left")
    result = processor.process([], 1.0)
    assert not result.armed
    assert result.actions == [KeyAction("left", False)]


def test_runner_profile_maps_swipe_right() -> None:
    processor = FrameProcessor()
    processor.set_mode("game", "temple-run")
    processor.armed = True
    processor.process([hand()], 0.0)
    result = processor.process([hand(shift=0.1)], 0.1)
    assert Tap("right") in result.actions


def test_runner_profile_maps_palm_up_to_jump() -> None:
    processor = FrameProcessor()
    processor.set_mode("game", "temple-run")
    processor.armed = True
    processor.process([hand()], 0.0)
    palm_up = hand()
    palm_up[8] = P(0.5, 0.2, 0.0)
    result = processor.process([palm_up], 0.1)
    assert Tap("jump") in result.actions


def test_fps_profile_emits_forward_key_action() -> None:
    processor = FrameProcessor()
    processor.set_mode("game", "counter-strike")
    processor.armed = True
    result = processor.process([hand()], 0.0)
    assert KeyAction("forward", True) in result.actions
