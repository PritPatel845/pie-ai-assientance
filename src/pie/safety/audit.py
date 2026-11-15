from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any

_LOG = logging.getLogger(__name__)
_MAX_BYTES = 5 * 1024 * 1024
_BACKUPS = 5


def redact(value: Any, *, tool: str = "", key: str = "") -> Any:
    lowered = key.casefold()
    if any(word in lowered for word in ("password", "token", "secret", "key", "authorization")):
        return "***"
    if tool == "mac.type_text" and key == "text":
        return {"length": len(str(value))}
    if tool == "fs.write_text" and key == "content":
        return {"length": len(str(value))}
    if isinstance(value, dict):
        return {str(name): redact(item, tool=tool, key=str(name)) for name, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(item, tool=tool) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


class AuditLog:
    """Append-only JSONL audit writer. Audit failures never block tool execution."""

    def __init__(self, path: str | Path, *, max_bytes: int = _MAX_BYTES) -> None:
        self.path = Path(path).expanduser()
        self.max_bytes = max_bytes
        self._lock = threading.Lock()

    def _rotate(self) -> None:
        if not self.path.exists() or self.path.stat().st_size < self.max_bytes:
            return
        oldest = self.path.with_name(self.path.name + f".{_BACKUPS}")
        oldest.unlink(missing_ok=True)
        for index in range(_BACKUPS - 1, 0, -1):
            source = self.path.with_name(self.path.name + f".{index}")
            if source.exists():
                source.replace(self.path.with_name(self.path.name + f".{index + 1}"))
        self.path.replace(self.path.with_name(self.path.name + ".1"))

    def write(self, record: dict[str, Any]) -> bool:
        safe = dict(record)
        safe["ts"] = safe.get("ts", time.time())
        safe["args"] = redact(safe.get("args", {}), tool=str(safe.get("tool", "")))
        try:
            encoded = json.dumps(safe, ensure_ascii=False, separators=(",", ":"), default=str) + "\n"
            with self._lock:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                self._rotate()
                descriptor = os.open(
                    self.path,
                    os.O_WRONLY | os.O_CREAT | os.O_APPEND,
                    0o600,
                )
                try:
                    os.fchmod(descriptor, 0o600)
                    with os.fdopen(descriptor, "a", encoding="utf-8", closefd=False) as handle:
                        handle.write(encoded)
                        handle.flush()
                        os.fsync(handle.fileno())
                finally:
                    os.close(descriptor)
            return True
        except OSError as exc:
            _LOG.warning("Could not write audit record: %s", type(exc).__name__)
            return False


__all__ = ["AuditLog", "redact"]
