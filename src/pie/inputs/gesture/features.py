from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Protocol


class Landmark(Protocol):
    x: float
    y: float
    z: float


FINGERS: tuple[tuple[int, int], ...] = ((8, 6), (12, 10), (16, 14), (20, 18))


def distance(a: Landmark, b: Landmark) -> float:
    return math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2)


def hand_size(hand: Sequence[Landmark]) -> float:
    return max(distance(hand[0], hand[9]), 0.001)


def finger_extended(hand: Sequence[Landmark], tip: int, pip: int) -> bool:
    return hand[tip].y < hand[pip].y - 0.02


def is_pinch(hand: Sequence[Landmark]) -> bool:
    return distance(hand[4], hand[8]) / hand_size(hand) < 0.48


def is_open_palm(hand: Sequence[Landmark]) -> bool:
    return all(finger_extended(hand, tip, pip) for tip, pip in FINGERS)


def is_thumb_extended(hand: Sequence[Landmark]) -> bool:
    return (distance(hand[4], hand[0]) > distance(hand[3], hand[0])
            or distance(hand[4], hand[5]) > distance(hand[3], hand[5]))


def is_four_finger(hand: Sequence[Landmark]) -> bool:
    return is_open_palm(hand) and not is_thumb_extended(hand)


def is_fist(hand: Sequence[Landmark]) -> bool:
    return not any(finger_extended(hand, tip, pip) for tip, pip in FINGERS)


def is_two_finger(hand: Sequence[Landmark]) -> bool:
    return (finger_extended(hand, 8, 6) and finger_extended(hand, 12, 10)
            and not finger_extended(hand, 16, 14))


def is_three_finger(hand: Sequence[Landmark]) -> bool:
    return (finger_extended(hand, 8, 6) and finger_extended(hand, 12, 10)
            and finger_extended(hand, 16, 14) and not finger_extended(hand, 20, 18))


def is_thumb_up(hand: Sequence[Landmark]) -> bool:
    folded = all(not finger_extended(hand, tip, pip) for tip, pip in FINGERS)
    return folded and hand[4].y < hand[0].y - 0.08


def is_thumb_down(hand: Sequence[Landmark]) -> bool:
    folded = all(not finger_extended(hand, tip, pip) for tip, pip in FINGERS)
    return folded and hand[4].y > hand[0].y + 0.08


def classify_desktop(hand: Sequence[Landmark]) -> str:
    if is_thumb_up(hand):
        return "THUMB UP / PLAY"
    if is_thumb_down(hand):
        return "THUMB DOWN / STOP"
    if is_pinch(hand):
        return "PINCH / OPEN"
    if is_three_finger(hand):
        return "THREE FINGER / OPEN"
    if is_open_palm(hand):
        return "OPEN PALM"
    if is_fist(hand):
        return "FIST / VOICE"
    if is_two_finger(hand):
        return "TWO-FINGER SWIPE"
    return "INDEX / POINTER"


def normalize_hand(hand: Sequence[Landmark]) -> list[float]:
    if len(hand) != 21:
        raise ValueError("A hand must contain exactly 21 landmarks")
    wrist, middle = hand[0], hand[9]
    scale = max(distance(wrist, middle), 1e-6)
    dx, dy = middle.x - wrist.x, middle.y - wrist.y
    angle = math.atan2(dx, -dy)
    c, s = math.cos(angle), math.sin(angle)
    values: list[float] = []
    for point in hand:
        x, y = point.x - wrist.x, point.y - wrist.y
        values.extend(((c * x - s * y) / scale, (s * x + c * y) / scale,
                       (point.z - wrist.z) / scale))
    return values
