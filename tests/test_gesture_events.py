from __future__ import annotations

from pie.inputs.gesture import runner


def test_gesture_events_are_rising_edge_and_debounced(monkeypatch) -> None:
    monkeypatch.setattr(runner, "is_pinch", lambda hand: True)
    monkeypatch.setattr(runner, "is_open_palm", lambda hand: False)
    monkeypatch.setattr(runner, "is_fist", lambda hand: False)
    monkeypatch.setattr(runner, "is_thumb_up", lambda hand: False)
    monkeypatch.setattr(runner, "is_thumb_down", lambda hand: False)
    monkeypatch.setattr(runner, "is_two_finger", lambda hand: False)
    monkeypatch.setattr(runner, "is_three_finger", lambda hand: False)
    monkeypatch.setattr(runner, "is_four_finger", lambda hand: False)
    tracker = runner.GestureEventTracker()
    hand = [object()]
    assert tracker.update(hand, 1.0) == ("pinch",)
    assert tracker.update(hand, 1.1) == ()
    assert tracker.update((), 1.2) == ()
    assert tracker.update(hand, 1.2) == ()
    assert tracker.update((), 1.4) == ()
    assert tracker.update(hand, 1.4) == ("pinch",)


def test_gesture_event_tracker_handles_no_hand_reset(monkeypatch) -> None:
    monkeypatch.setattr(runner, "is_pinch", lambda hand: True)
    for name in ("is_open_palm", "is_fist", "is_thumb_up", "is_thumb_down",
                 "is_two_finger", "is_three_finger", "is_four_finger"):
        monkeypatch.setattr(runner, name, lambda hand: False)
    tracker = runner.GestureEventTracker()
    assert tracker.update([[object()]], 2.0) == ("pinch",)
    assert tracker.update([], 2.1) == ()
    assert tracker.update([[object()]], 2.2) == ()
