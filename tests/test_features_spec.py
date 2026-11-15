"""Pure landmark predicates and normalization follow Phase 0S sections 3.1 and 3.2."""

from __future__ import annotations

import math
from dataclasses import dataclass

import pytest

from pie.inputs.gesture.features import (
    classify_desktop,
    distance,
    finger_extended,
    hand_size,
    is_fist,
    is_four_finger,
    is_open_palm,
    is_pinch,
    is_three_finger,
    is_thumb_down,
    is_thumb_up,
    is_two_finger,
    normalize_hand,
)


@dataclass
class Point:
    x: float
    y: float
    z: float = 0.0


def make_hand(*, extended=(True, True, True, True), thumb=(0.2, 0.4, 0.0), index_tip=None):
    hand = [Point(0.5, 0.7, 0.0) for _ in range(21)]
    hand[0] = Point(0.5, 0.8, 0.0)
    hand[9] = Point(0.5, 0.5, 0.0)
    for (tip, pip), is_up in zip(((8, 6), (12, 10), (16, 14), (20, 18)), extended, strict=True):
        hand[pip] = Point(0.5, 0.6, 0.0)
        hand[tip] = Point(0.5, 0.3 if is_up else 0.68, 0.0)
    hand[3] = Point(0.25, 0.55, 0.0)
    hand[4] = Point(*thumb)
    if index_tip is not None:
        hand[8] = Point(*index_tip)
    return hand


def test_distance_and_hand_size() -> None:
    assert distance(Point(0, 0), Point(3, 4)) == 5
    assert hand_size(make_hand()) == pytest.approx(0.3)


def test_finger_extension_boundary_is_strict() -> None:
    hand = make_hand()
    hand[6] = Point(0.0, 0.5)
    hand[8] = Point(0.0, 0.48)
    assert not finger_extended(hand, 8, 6)
    hand[8] = Point(0.0, 0.479)
    assert finger_extended(hand, 8, 6)


def test_open_palm_fist_and_finger_counts() -> None:
    assert is_open_palm(make_hand())
    assert is_fist(make_hand(extended=(False, False, False, False)))
    assert is_two_finger(make_hand(extended=(True, True, False, False)))
    assert is_three_finger(make_hand(extended=(True, True, True, False)))
    assert is_four_finger(make_hand(thumb=(0.45, 0.75, 0.0)))


def test_thumb_up_and_down() -> None:
    assert is_thumb_up(make_hand(extended=(False, False, False, False), thumb=(0.5, 0.6, 0.0)))
    assert is_thumb_down(make_hand(extended=(False, False, False, False), thumb=(0.5, 1.0, 0.0)))


def test_pinch_is_normalized_by_hand_size() -> None:
    hand = make_hand(index_tip=(0.51, 0.8, 0.0), thumb=(0.5, 0.8, 0.0))
    assert is_pinch(hand)


def test_normalize_hand_is_translation_scale_and_rotation_invariant() -> None:
    original = [Point(i * 0.01, i * 0.02, i * 0.003) for i in range(21)]
    translated_scaled = [Point(7 + p.x * 3, -4 + p.y * 3, 2 + p.z * 3) for p in original]
    first = normalize_hand(original)
    second = normalize_hand(translated_scaled)
    assert len(first) == 63
    assert max(abs(a - b) for a, b in zip(first, second, strict=True)) < 1e-6
    assert all(math.isfinite(value) for value in first)


def test_classification_precedence_is_stable() -> None:
    thumb_up = make_hand(extended=(False, False, False, False), thumb=(0.5, 0.6, 0.0))
    assert classify_desktop(thumb_up) == "THUMB UP / PLAY"
