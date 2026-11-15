from __future__ import annotations

from collections import deque
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

Audio = NDArray[np.float32]


@dataclass(frozen=True, slots=True)
class Segment:
    audio: Audio
    started_at: float
    ended_at: float


class EnergyVad:
    """Deterministic energy VAD; timestamps are derived only from sample counts."""

    def __init__(
        self,
        *,
        sample_rate: int = 16_000,
        threshold: float = 0.015,
        min_speech_ms: int = 150,
        end_silence_ms: int = 600,
        max_utterance_s: float = 12.0,
        pre_roll_ms: int = 200,
    ) -> None:
        if sample_rate <= 0 or threshold <= 0:
            raise ValueError("sample_rate and threshold must be positive")
        if min_speech_ms <= 0 or end_silence_ms <= 0 or max_utterance_s <= 0:
            raise ValueError("VAD durations must be positive")
        self.sample_rate = sample_rate
        self.threshold = threshold
        self.min_speech_samples = sample_rate * max(min_speech_ms, 300) // 1000
        self.end_silence_samples = sample_rate * end_silence_ms // 1000
        self.max_samples = int(sample_rate * max_utterance_s)
        self.pre_roll_samples = sample_rate * pre_roll_ms // 1000
        self._pre_roll: deque[Audio] = deque()
        self._pre_roll_count = 0
        self._candidate: list[Audio] = []
        self._candidate_count = 0
        self._speech: list[Audio] = []
        self._speech_count = 0
        self._silence_count = 0
        self._sample_cursor = 0
        self._started_at = 0
        self._noise_floor = 0.003

    @staticmethod
    def _rms(block: Audio) -> float:
        if block.size == 0:
            return 0.0
        return float(np.sqrt(np.mean(np.square(block, dtype=np.float64))))

    def _remember_pre_roll(self, block: Audio) -> None:
        self._pre_roll.append(block.copy())
        self._pre_roll_count += block.size
        while self._pre_roll and self._pre_roll_count > self.pre_roll_samples:
            excess = self._pre_roll_count - self.pre_roll_samples
            first = self._pre_roll[0]
            if first.size <= excess:
                self._pre_roll.popleft()
                self._pre_roll_count -= first.size
            else:
                self._pre_roll[0] = first[excess:].copy()
                self._pre_roll_count -= excess

    def _finish(self, end_sample: int) -> Segment | None:
        if not self._speech:
            return None
        audio = np.concatenate(self._speech).astype(np.float32, copy=False)
        segment = Segment(
            audio=audio,
            started_at=self._started_at / self.sample_rate,
            ended_at=end_sample / self.sample_rate,
        )
        self._speech.clear()
        self._speech_count = 0
        self._silence_count = 0
        self._candidate.clear()
        self._candidate_count = 0
        return segment

    def feed(self, block: Audio) -> list[Segment]:
        samples = np.asarray(block, dtype=np.float32).reshape(-1)
        if samples.size == 0:
            return []
        rms = self._rms(samples)
        is_speech = rms >= max(self.threshold, self._noise_floor * 3.0)
        start_sample = self._sample_cursor
        self._sample_cursor += samples.size
        output: list[Segment] = []

        if self._speech_count == 0:
            if not is_speech:
                self._noise_floor = 0.98 * self._noise_floor + 0.02 * rms
                self._remember_pre_roll(samples)
                return output
            self._candidate.append(samples.copy())
            self._candidate_count += samples.size
            if self._candidate_count < self.min_speech_samples:
                return output
            self._speech = [part.copy() for part in self._pre_roll]
            self._speech.extend(self._candidate)
            self._speech_count = self._pre_roll_count + self._candidate_count
            self._started_at = max(0, start_sample - self._candidate_count - self._pre_roll_count)
            self._candidate.clear()
            self._candidate_count = 0
            self._pre_roll.clear()
            self._pre_roll_count = 0
        elif is_speech:
            self._speech.append(samples.copy())
            self._speech_count += samples.size
            self._silence_count = 0
        else:
            self._speech.append(samples.copy())
            self._speech_count += samples.size
            self._silence_count += samples.size

        if self._speech_count >= self.max_samples:
            segment = self._finish(start_sample + samples.size)
            if segment is not None:
                output.append(segment)
            self._pre_roll.clear()
            self._pre_roll_count = 0
        elif self._silence_count >= self.end_silence_samples:
            segment = self._finish(start_sample + samples.size)
            if segment is not None:
                output.append(segment)
            self._remember_pre_roll(samples)
        return output
