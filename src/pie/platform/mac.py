from __future__ import annotations

import subprocess
from collections.abc import Callable, Sequence

Runner = Callable[..., subprocess.CompletedProcess[str]]


class MacController:
    """Small macOS action boundary; construction is safe on non-macOS systems."""

    def __init__(self, runner: Runner = subprocess.run) -> None:
        self._runner = runner

    def _run(self, argv: Sequence[str], timeout: float = 5.0) -> bool:
        if not argv or argv[0] not in {"/usr/bin/open", "/usr/bin/osascript"}:
            raise ValueError("Executable is not allow-listed")
        try:
            result = self._runner(list(argv), capture_output=True, text=True,
                                  timeout=timeout, check=False, shell=False)
        except (OSError, subprocess.TimeoutExpired):
            return False
        return result.returncode == 0

    def open_target(self, target: str) -> bool:
        return self._run(("/usr/bin/open", target))

    def open_application(self, name: str) -> bool:
        if not name.strip():
            return False
        return self._run(("/usr/bin/open", "-a", name.strip()))

    def mute(self) -> bool:
        return self._run(("/usr/bin/osascript", "-e", "set volume output muted true"))

    def set_volume(self, value: int) -> bool:
        clamped = max(0, min(100, int(value)))
        return self._run(("/usr/bin/osascript", "-e", f"set volume output volume {clamped}"))
