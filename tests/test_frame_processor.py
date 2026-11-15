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


def hand(*, extended=(True, True, True, True), thumb_x=0.35, thumb_y=0.3, z=0.0, shift=0.0):
    points = [P(0.5 + shift, 0.7, z) for _ in range(21)]
    points[0] = P(0.5 + shift, 0.8, z)
    points[9] = P(0.5 + shift, 0.5, z)
    for (tip, pip), is_up in zip(((8, 6), (12, 10), (16, 14), (20, 18)), extended, strict=False):
        points[pip] = P(0.5 + shift, 0.6, z)
        points[tip] = P(0.5 + shift, 0.3 if is_up else 0.68, z)
    points[4] = P(thumb_x + shift, thumb_y, z)
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


def test_mode_switch_resets_previous_desktop_scroll_position() -> None:
    processor = FrameProcessor(arm_hold_seconds=0)
    palm = hand()
    processor.process([palm], 0.0)
    processor.process([palm], 0.1)
    two_finger = hand(extended=(True, True, False, False))
    processor.process([two_finger], 0.2)
    processor.set_mode("game")
    processor.set_mode("desktop")
    processor.process([palm], 1.0)
    processor.process([palm], 1.1)
    two_finger[8] = P(0.9, 0.3)
    result = processor.process([two_finger], 1.2)
    assert not any(type(action).__name__ == "Scroll" for action in result.actions)


def arm(processor: FrameProcessor, palm, start: float = 0.0) -> None:
    processor.process([palm], start)
    processor.process([palm], start + 0.01)
    assert processor.armed


def test_desktop_pinch_double_click_debounce() -> None:
    from pie.inputs.gesture.frame import DoubleClick

    processor = FrameProcessor(arm_hold_seconds=0)
    arm(processor, hand())
    pinch = hand(extended=(True, False, False, False), thumb_x=0.38)
    assert DoubleClick() in processor.process([pinch], 0.1).actions
    processor.process([hand()], 0.2)
    assert DoubleClick() not in processor.process([pinch], 0.6).actions
    processor.process([hand()], 0.7)
    assert DoubleClick() in processor.process([pinch], 0.9).actions


def test_desktop_three_finger_rising_edge_double_clicks() -> None:
    from pie.inputs.gesture.frame import DoubleClick

    processor = FrameProcessor(arm_hold_seconds=0)
    arm(processor, hand())
    three = hand(extended=(True, True, True, False))
    assert DoubleClick() in processor.process([three], 0.1).actions
    assert DoubleClick() not in processor.process([three], 0.2).actions


def test_desktop_open_palm_depth_triggers_mute_once() -> None:
    from pie.inputs.gesture.frame import Mute

    processor = FrameProcessor(arm_hold_seconds=0)
    deep_palm = hand(z=-0.2)
    processor.process([deep_palm], 0.0)
    result = processor.process([deep_palm], 0.01)
    assert Mute() in result.actions
    assert Mute() not in processor.process([deep_palm], 0.02).actions


def test_desktop_fist_runs_voice_command_on_rising_edge() -> None:
    from pie.inputs.gesture.frame import RunVoiceCommand

    processor = FrameProcessor(arm_hold_seconds=0)
    arm(processor, hand())
    fist = hand(extended=(False, False, False, False), thumb_y=0.75)
    assert RunVoiceCommand() in processor.process([fist], 0.1).actions
    assert RunVoiceCommand() not in processor.process([fist], 0.2).actions


def test_desktop_thumb_gestures_emit_media_actions() -> None:
    from pie.inputs.gesture.frame import PlayMedia, StopMedia

    processor = FrameProcessor(arm_hold_seconds=0)
    arm(processor, hand())
    thumb_up = hand(extended=(False, False, False, False), thumb_y=0.3)
    thumb_down = hand(extended=(False, False, False, False), thumb_y=1.0)
    assert PlayMedia() in processor.process([thumb_up], 0.1).actions
    processor.process([hand()], 0.2)
    assert StopMedia() in processor.process([thumb_down], 0.3).actions


def test_two_finger_scroll_threshold_and_direction() -> None:
    from pie.inputs.gesture.frame import Scroll

    processor = FrameProcessor(arm_hold_seconds=0)
    arm(processor, hand())
    two = hand(extended=(True, True, False, False))
    processor.process([two], 0.1)
    right = hand(extended=(True, True, False, False), shift=0.09)
    assert Scroll(-5) in processor.process([right], 0.2).actions
    left = hand(extended=(True, True, False, False), shift=0.0)
    assert Scroll(5) in processor.process([left], 0.3).actions


def test_volume_filter_emits_on_two_point_change_or_elapsed_interval() -> None:
    from pie.inputs.gesture.frame import SetVolume

    processor = FrameProcessor(arm_hold_seconds=0)
    palm = hand()
    processor.process([palm], 0.0)
    first = processor.process([palm], 0.01)
    assert SetVolume(72) in first.actions
    one_step = hand(z=0.005)
    assert not any(
        isinstance(action, SetVolume) for action in processor.process([one_step], 0.1).actions
    )
    elapsed = processor.process([one_step], 0.22)
    assert SetVolume(71) in elapsed.actions


def arm_game(processor: FrameProcessor) -> None:
    palm = hand()
    processor.process([palm], 0.0)
    assert processor.process([palm], 2.1).armed


def test_unarmed_desktop_emits_no_actions_for_every_pose() -> None:
    from pie.inputs.gesture.frame import FrameProcessor

    poses = [
        hand(),
        hand(extended=(False, False, False, False), thumb_y=0.75),
        hand(extended=(True, False, False, False), thumb_x=0.38),
        hand(extended=(False, False, False, False), thumb_y=0.3),
        hand(extended=(False, False, False, False), thumb_y=1.0),
        hand(extended=(True, True, False, False)),
        hand(extended=(True, True, True, False)),
        hand(thumb_x=0.45, thumb_y=0.75),
        hand(extended=(True, False, False, False), thumb_x=0.25, thumb_y=0.55),
    ]
    for pose in poses:
        processor = FrameProcessor(arm_hold_seconds=2.0)
        result = processor.process([pose], 0.0)
        assert not result.armed
        assert result.actions == []


def test_racing_profile_emits_exact_key_states_for_three_and_four_finger_poses(
) -> None:
    processor = FrameProcessor()
    processor.set_mode("game", "asphalt")
    arm_game(processor)

    three = hand(extended=(True, True, True, False))
    assert processor.process([three], 2.2).actions == [
        KeyAction("left", True),
        KeyAction("accelerate", True),
    ]

    four = hand(thumb_x=0.45, thumb_y=0.75)
    assert processor.process([four], 2.3).actions == [
        KeyAction("left", False),
        KeyAction("right", True),
    ]


def test_racing_profile_drift_brake_and_nitro_sequences() -> None:
    processor = FrameProcessor()
    processor.set_mode("game", "asphalt")
    arm_game(processor)

    drifting_left = hand(extended=(True, True, False, False), shift=-0.1)
    actions = processor.process([drifting_left], 2.2).actions
    assert actions == [KeyAction("left", True), KeyAction("brake", True)]

    fist = hand(extended=(False, False, False, False), thumb_y=0.75)
    actions = processor.process([fist], 2.3).actions
    assert KeyAction("left", False) in actions
    assert KeyAction("brake", True) not in actions

    pinch = hand(extended=(True, False, False, False), thumb_x=0.38)
    actions = processor.process([pinch], 2.4).actions
    assert Tap("nitro") in actions


def test_runner_profile_covers_pose_taps_and_held_slide() -> None:
    processor = FrameProcessor()
    processor.set_mode("game", "temple-run")
    arm_game(processor)

    three = hand(extended=(True, True, True, False))
    assert processor.process([three], 2.2).actions == [Tap("left")]

    four = hand(thumb_x=0.45, thumb_y=0.75)
    assert processor.process([four], 2.3).actions == [Tap("right")]

    fist = hand(extended=(False, False, False, False), thumb_y=0.75)
    assert processor.process([fist], 2.4).actions == [KeyAction("slide", True)]
    assert processor.process([fist], 2.5).actions == []
    two_finger = hand(extended=(True, True, False, False))
    assert processor.process([two_finger], 2.6).actions == [KeyAction("slide", False)]


def test_fps_profile_covers_directional_keys_click_and_jump() -> None:
    from pie.inputs.gesture.frame import MouseClick

    processor = FrameProcessor()
    processor.set_mode("game", "counter-strike")
    arm_game(processor)

    assert processor.process([hand()], 2.2).actions == [KeyAction("forward", True)]

    three = hand(extended=(True, True, True, False))
    assert KeyAction("left", True) in processor.process([three], 2.3).actions

    four = hand(thumb_x=0.45, thumb_y=0.75)
    actions = processor.process([four], 2.4).actions
    assert KeyAction("left", False) in actions
    assert KeyAction("right", True) in actions

    fist = hand(extended=(False, False, False, False), thumb_y=0.75)
    actions = processor.process([fist], 2.5).actions
    assert KeyAction("right", False) in actions
    assert KeyAction("back", True) in actions

    pinch = hand(extended=(True, False, False, False), thumb_x=0.38)
    assert MouseClick() in processor.process([pinch], 2.6).actions

    thumb_up = hand(extended=(False, False, False, False), thumb_y=0.3)
    assert Tap("jump") in processor.process([thumb_up], 2.7).actions

