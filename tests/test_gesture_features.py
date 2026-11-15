from dataclasses import dataclass

import pytest

from pie.inputs.gesture.features import normalize_hand


@dataclass
class P:
    x: float
    y: float
    z: float = 0.0


def test_normalize_hand_requires_21_landmarks() -> None:
    with pytest.raises(ValueError):
        normalize_hand([P(0, 0)])


def test_normalized_hand_has_63_values() -> None:
    hand = [P(float(i % 3), float(i), 0.0) for i in range(21)]
    assert len(normalize_hand(hand)) == 63
