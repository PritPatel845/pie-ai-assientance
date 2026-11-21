from __future__ import annotations

# Ruff's import sorter disagrees on this third-party pair; keep the test imports explicit.
# ruff: noqa: I001

import pytest
import numpy as np

from pie.inputs.voice.vad import EnergyVad


RATE = 16_000
BLOCK = 512


def tone(samples: int, amplitude: float = 0.08) -> np.ndarray:
    x = np.arange(samples, dtype=np.float32)
    return (amplitude * np.sin(2 * np.pi * 440 * x / RATE)).astype(np.float32)


def feed_ms(vad: EnergyVad, milliseconds: int, amplitude: float) -> list:
    samples = int(RATE * milliseconds / 1000)
    signal = tone(samples, amplitude)
    segments = []
    for start in range(0, samples, BLOCK):
        segments.extend(vad.feed(signal[start : start + BLOCK]))
    return segments


def test_silence_and_low_noise_do_not_create_segments() -> None:
    vad = EnergyVad()
    assert feed_ms(vad, 2000, 0.001) == []
    assert feed_ms(vad, 1000, 0.0) == []


def test_one_second_speech_ends_after_silence() -> None:
    vad = EnergyVad()
    assert feed_ms(vad, 1000, 0.08) == []
    segments = feed_ms(vad, 700, 0.0)
    assert len(segments) == 1
    assert 0.9 <= len(segments[0].audio) / RATE <= 1.7
    assert segments[0].started_at >= 0
    assert segments[0].ended_at > segments[0].started_at


def test_short_gap_merges_two_bursts() -> None:
    vad = EnergyVad()
    feed_ms(vad, 500, 0.08)
    feed_ms(vad, 400, 0.0)
    feed_ms(vad, 500, 0.08)
    segments = feed_ms(vad, 700, 0.0)
    assert len(segments) == 1


def test_long_gap_splits_two_bursts() -> None:
    vad = EnergyVad()
    feed_ms(vad, 500, 0.08)
    first = feed_ms(vad, 700, 0.0)
    feed_ms(vad, 500, 0.08)
    second = feed_ms(vad, 700, 0.0)
    assert len(first) == 1
    assert len(second) == 1


def test_utterance_is_capped() -> None:
    vad = EnergyVad(max_utterance_s=2.0)
    segments = feed_ms(vad, 2600, 0.08)
    assert len(segments) == 1
    assert len(segments[0].audio) <= int(RATE * 2.1)


def test_preroll_is_included() -> None:
    vad = EnergyVad()
    feed_ms(vad, 200, 0.0)
    feed_ms(vad, 500, 0.08)
    segments = feed_ms(vad, 700, 0.0)
    assert len(segments) == 1
    assert len(segments[0].audio) >= int(RATE * 0.5)


def test_invalid_vad_parameters_are_rejected() -> None:
    with pytest.raises(ValueError):
        EnergyVad(threshold=0)


def test_speech_must_be_consecutive_and_at_least_300ms() -> None:
    vad = EnergyVad()
    assert feed_ms(vad, 200, 0.08) == []
    assert feed_ms(vad, 400, 0.0) == []
    assert feed_ms(vad, 200, 0.08) == []
    assert feed_ms(vad, 700, 0.0) == []
    assert feed_ms(vad, 350, 0.08) == []
    assert len(feed_ms(vad, 700, 0.0)) == 1


def test_adaptive_noise_floor_tracks_a_quiet_room() -> None:
    vad = EnergyVad(threshold=0.001)
    initial = vad._noise_floor
    feed_ms(vad, 2000, 0.01)
    assert vad._noise_floor > initial
    assert feed_ms(vad, 700, 0.0) == []


def test_reset_discards_preroll_and_partial_speech() -> None:
    vad = EnergyVad()
    feed_ms(vad, 500, 0.08)
    vad.reset()
    feed_ms(vad, 400, 0.0)
    assert feed_ms(vad, 350, 0.08) == []
    segments = feed_ms(vad, 700, 0.0)
    assert len(segments) == 1
    assert len(segments[0].audio) < int(RATE * 1.2)
