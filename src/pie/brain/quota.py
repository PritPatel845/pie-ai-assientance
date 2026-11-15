from __future__ import annotations

import json
import logging
import os
import threading
import time
from collections.abc import Callable
from pathlib import Path

_LOG = logging.getLogger(__name__)


class QuotaTracker:
    def __init__(
        self,
        path: Path | None = None,
        *,
        default_cooldown_s: int = 3600,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.path = path or Path.home() / ".pie" / "state" / "quota.json"
        self.default_cooldown_s = default_cooldown_s
        self.clock = clock
        self._lock = threading.RLock()
        self._state: dict[str, dict[str, object]] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(value, dict):
                raise ValueError("quota state must be an object")
            self._state = {str(key): item for key, item in value.items() if isinstance(item, dict)}
        except (OSError, ValueError, json.JSONDecodeError):
            corrupt = self.path.with_name(f"{self.path.name}.corrupt-{int(self.clock())}")
            try:
                os.replace(self.path, corrupt)
            except OSError:
                _LOG.warning("Could not preserve corrupt quota state file")
            _LOG.warning("Corrupt quota state recovered as empty")

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps(self._state, sort_keys=True), encoding="utf-8")
        os.replace(temporary, self.path)

    def mark_exhausted(self, provider: str, reset_at: float | None = None) -> None:
        now = self.clock()
        until = reset_at if reset_at is not None else now + self.default_cooldown_s
        with self._lock:
            self._state[provider] = {
                "exhausted_until": until,
                "reason": "quota exhausted",
                "since": now,
            }
            self._save()

    def is_available(self, provider: str, now: float | None = None) -> bool:
        current = self.clock() if now is None else now
        with self._lock:
            item = self._state.get(provider)
            if item is None:
                return True
            until = item.get("exhausted_until")
            if until is None:
                return True
            if isinstance(until, bool) or not isinstance(until, int | float):
                return False
            return float(until) <= current

    def reset(self, provider: str | None = None) -> None:
        with self._lock:
            if provider is None:
                self._state.clear()
            else:
                self._state.pop(provider, None)
            self._save()

    def snapshot(self) -> dict[str, dict[str, object]]:
        with self._lock:
            return {key: dict(value) for key, value in self._state.items()}
