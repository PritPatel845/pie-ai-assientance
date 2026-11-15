"""Game gesture precedence follows Phase 0S section 3.2."""
from __future__ import annotations

from dataclasses import dataclass

from pie.inputs.gesture.game import game_gesture


@dataclass
class P:
    x: float
    y: float
    z: float = 0.0


def make_hand(extended=(True, True, True, True), thumb=(0.2, 0.4, 0.0)):
    hand = [P(0.5, 0.7, 0.0) for _ in range(21)]
    hand[0] = P(0.5, 0.8, 0.0)
    hand[9] = P(0.5, 0.5, 0.0)
    for (tip, pip), up in zip(((8, 6), (12, 10), (16, 14), (20, 18)),
                              extended, strict=True):
        hand[pip] = P(0.5, 0.6, 0.0)
        hand[tip] = P(0.5, 0.3 if up else 0.68, 0.0)
    hand[4] = P(*thumb)
    return hand


def test_open_thumb_extended_is_not_four_finger_right() -> None:
    hand = make_hand(thumb=(0.2, 0.4, 0.0))
    assert game_gesture(hand, None, hand[8]) == "GAME READY"


def test_swipe_left_and_right() -> None:
    hand = make_hand()
    assert game_gesture(hand, P(0.0, 0.5), P(0.1, 0.5)) == "SWIPE RIGHT"
    assert game_gesture(hand, P(0.1, 0.5), P(0.0, 0.5)) == "SWIPE LEFT"


def test_palm_up_and_down() -> None:
    hand = make_hand()
    assert game_gesture(hand, P(0.5, 0.6), P(0.5, 0.5)) == "PALM UP / JUMP"
    assert game_gesture(hand, P(0.5, 0.5), P(0.5, 0.6)) == "PALM DOWN / SLIDE"
