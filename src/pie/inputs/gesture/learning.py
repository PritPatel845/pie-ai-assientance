from __future__ import annotations

import json
import os
import time
from collections import deque
from collections.abc import Callable, Sequence
from pathlib import Path

from pie.inputs.gesture.features import Landmark, normalize_hand


class LearningEngine:
    def __init__(
        self, base_dir: Path | str | None = None, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self.base_dir = Path(base_dir) if base_dir else Path.home() / ".pie" / "learning"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._clock = clock
        self._samples: deque[dict[str, object]] = deque(maxlen=5000)
        self._voice: list[str] = []
        self._last_sample = float("-inf")
        self._last_flush = self._clock()
        self._load()

    def _load(self) -> None:
        path = self.base_dir / "learning.json"
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("Learning data must be a JSON object")
            samples = data.get("samples", [])
            voice = data.get("voice", [])
            if not isinstance(samples, list) or not all(
                isinstance(sample, dict) for sample in samples
            ):
                raise ValueError("Learning samples must be a list of objects")
            if not isinstance(voice, list) or not all(
                isinstance(command, str) for command in voice
            ):
                raise ValueError("Learning voice history must be a list of strings")
            self._samples.extend(samples)
            self._voice.extend(voice)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            corrupt = path.with_name(f"{path.name}.corrupt-{int(self._clock())}")
            path.replace(corrupt)

    def record_hand_sample(self, hand: Sequence[Landmark], gesture: str) -> dict[str, object]:
        now = self._clock()
        sample: dict[str, object] = {
            "time": now,
            "gesture": gesture,
            "signature": normalize_hand(hand),
        }
        if now - self._last_sample >= 0.25:
            self._samples.append(sample)
            self._last_sample = now
        if now - self._last_flush >= 5:
            self.flush()
        return sample

    def record_voice_command(self, command: str) -> None:
        cleaned = command.strip().lower()
        self._voice.append("type <redacted>" if cleaned.startswith("type ") else cleaned)

    def gesture_history(self) -> list[dict[str, object]]:
        return list(self._samples)

    def profile_snapshot(self) -> dict[str, object]:
        return {
            "user_id": "local",
            "gesture_patterns": len(self._samples),
            "voice_patterns": len(self._voice),
            "comfort": {},
        }

    def adaptation_plan(self) -> dict[str, object]:
        return {
            "recommended_actions": [],
            "profile_summary": self.profile_snapshot(),
            "suggestions": [],
        }

    def suggested_features(self, limit: int = 5) -> list[str]:
        del limit
        return []

    def flush(self) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        path = self.base_dir / "learning.json"
        temp = path.with_suffix(".json.tmp")
        payload = {"samples": list(self._samples), "voice": self._voice}
        temp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        os.replace(temp, path)
        self._last_flush = self._clock()

    def close(self) -> None:
        self.flush()
