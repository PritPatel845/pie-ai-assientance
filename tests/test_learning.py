"""LearningEngine buffering, sampling, persistence, and redaction follow Phase 0S §3.4 (PDF pp. 19–20)."""

from __future__ import annotations

import json
from dataclasses import dataclass

from pie.inputs.gesture.learning import LearningEngine


@dataclass
class P:
    x: float
    y: float
    z: float = 0.0


def hand():
    return [P(i / 20, i / 30, 0.0) for i in range(21)]


def test_learning_rate_limit_and_persistence(tmp_path) -> None:
    now = [0.0]
    engine = LearningEngine(tmp_path, clock=lambda: now[0])
    engine.record_hand_sample(hand(), "OPEN PALM")
    now[0] = 0.1
    engine.record_hand_sample(hand(), "OPEN PALM")
    assert len(engine.gesture_history()) == 1
    now[0] = 0.3
    engine.record_hand_sample(hand(), "FIST")
    engine.record_voice_command("type my password")
    engine.close()
    payload = json.loads((tmp_path / "learning.json").read_text())
    assert len(payload["samples"]) == 2
    assert payload["voice"] == ["type <redacted>"]


def test_learning_ring_buffer_is_bounded(tmp_path) -> None:
    now = [0.0]
    engine = LearningEngine(tmp_path, clock=lambda: now[0])
    for index in range(5100):
        now[0] = index * 0.26
        engine.record_hand_sample(hand(), "gesture")
        engine._last_flush = now[0]  # isolate ring-buffer bounds from disk flush cost
    assert len(engine.gesture_history()) == 5000
