from __future__ import annotations

import logging
import queue
import re
import subprocess
import threading
from dataclasses import dataclass
from collections.abc import Callable\nfrom typing import Any

from pie.events import EventBus

_LOG = logging.getLogger(__name__)
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def sanitise_speech(text: str) -> str:
    return " ".join(_CONTROL.sub(" ", text).split())[:1000]


@dataclass(frozen=True, slots=True)
class Speech:
    text: str
    interrupt: bool = False


class Speaker:
    """Queued macOS speech worker with an interruptible subprocess."""

    def __init__(
        self,
        bus: EventBus,
        *,
        enabled: bool = True,
        voice: str = "Samantha",
        rate: int = 185,
        runner: Callable[..., Any] = subprocess.run,
        popen: Callable[..., Any] = subprocess.Popen,
    ) -> None:
        self.bus = bus
        self.enabled = enabled
        self.voice = voice
        self.rate = rate
        self.runner = runner
        self.popen = popen
        self.echo_guard = threading.Event()
        self._queue: queue.Queue[Speech | None] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._process: Any | None = None
        self._lock = threading.Lock()
        self._unsubscribe: Callable[[], None] | None = None
        self._voices: set[str] | None = None
        self._fallback_logged = False

    def start(self) -> None:
        if not self.enabled or self._thread is not None:
            return
        self._unsubscribe = self.bus.subscribe("tts.say", self._on_event, name="pie-tts")
        self._thread = threading.Thread(target=self._run, name="pie-tts", daemon=True)
        self._thread.start()

    def _on_event(self, event: Any) -> None:
        payload = event.payload
        text = sanitise_speech(str(payload.get("text", "")))
        if not text:
            return
        if bool(payload.get("interrupt", False)):
            self.interrupt()
        self._queue.put(Speech(text))

    def _available_voices(self) -> set[str]:
        if self._voices is None:
            result = self.runner(
                ["/usr/bin/say", "-v", "?"], capture_output=True, text=True,
                timeout=3, check=False, shell=False,
            )
            names = set()
            for line in (result.stdout or "").splitlines():
                match = re.match(r"^\s*([^\s#]+)", line)
                if match:
                    names.add(match.group(1))
            self._voices = names
        return self._voices

    def _run(self) -> None:
        while True:
            item = self._queue.get()
            if item is None:
                return
            voice = self.voice
            try:
                if voice not in self._available_voices():
                    voice = "Samantha" if "Samantha" in self._available_voices() else "Alex"
                    if not self._fallback_logged:
                        _LOG.warning("Configured TTS voice unavailable; using macOS default")
                        self._fallback_logged = True
                with self._lock:
                    self.echo_guard.set()
                    self._process = self.popen(
                        ["/usr/bin/say", "-v", voice, "-r", str(self.rate), "-f", "-"],
                        stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL, text=True, shell=False,
                    )
                    process = self._process
                if process.stdin is not None:
                    process.stdin.write(item.text)
                    process.stdin.close()
                process.wait(timeout=max(10, len(item.text) / 8))
            except (OSError, subprocess.SubprocessError, BrokenPipeError):
                _LOG.warning("macOS speech playback failed", exc_info=True)
            finally:
                with self._lock:
                    self._process = None
                    self.echo_guard.clear()

    def interrupt(self) -> None:
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
        with self._lock:
            process = self._process
            if process is not None and process.poll() is None:
                process.terminate()

    def stop(self) -> None:
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None
        self.interrupt()
        if self._thread is not None:
            self._queue.put(None)
            self._thread.join(timeout=2)
            self._thread = None


__all__ = ["Speaker", "Speech", "sanitise_speech"]
