from __future__ import annotations

import logging
import queue
import threading
import time
from collections.abc import Callable
from typing import Any

import numpy as np

from pie.config import VoiceConfig
from pie.events import EventBus
from pie.inputs.voice.commands import extract_wake_command
from pie.inputs.voice.executor import VoiceController as _VoiceController
from pie.inputs.voice.stt import Transcriber, create_transcriber, is_hallucination
from pie.inputs.voice.tts import Speaker
from pie.inputs.voice.vad import EnergyVad, Segment
from pie.inputs.voice.wake import TextWake

_LOG = logging.getLogger(__name__)
_SAMPLE_RATE = 16_000
_BLOCK_SIZE = 512


class VoiceController(_VoiceController):
    """Local microphone, VAD, STT, wake gating and legacy command integration."""

    def __init__(
        self,
        controller: Any,
        *,
        no_actions: bool = False,
        listen_seconds: int = 20,
        learning_engine: Any | None = None,
        bus: EventBus | None = None,
        language: str = "en",
        config: VoiceConfig | None = None,
        stream_factory: Callable[..., Any] | None = None,
        transcriber_factory: Callable[..., Transcriber] = create_transcriber,
        clock: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], float] = time.time,
    ) -> None:
        super().__init__(
            controller,
            no_actions=no_actions,
            listen_seconds=listen_seconds,
            learning_engine=learning_engine,
        )
        self.bus = bus
        self.config = config or VoiceConfig(listen_seconds=listen_seconds, language=language)
        self.language = self.config.language
        self._stream_factory = stream_factory
        self._transcriber_factory = transcriber_factory
        self._clock = clock
        self._wall_clock = wall_clock
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._audio_queue: queue.Queue[np.ndarray] = queue.Queue(maxsize=200)
        self._dropped_blocks = 0
        self._speaker = Speaker(
            bus, enabled=self.config.tts_enabled, voice=self.config.tts_voice,
            rate=self.config.tts_rate,
        ) if bus is not None else None
        self._vad = EnergyVad(
            sample_rate=_SAMPLE_RATE,
            threshold=self.config.vad_threshold,
            min_speech_ms=self.config.vad_min_speech_ms,
            end_silence_ms=self.config.vad_end_silence_ms,
            max_utterance_s=self.config.vad_max_utterance_s,
        )
        self._wake = TextWake(self.config.wake_words)
        self._active_until = 0.0
        self._last_stt_activity = self._clock()
        self._transcriber: Transcriber | None = None
        self._last_zero_notice = 0.0
        self._all_zero_frames = 0

    @property
    def echo_guard(self) -> bool:
        return self._speaker.echo_guard.is_set() if self._speaker is not None else False

    def _publish(self, topic: str, payload: dict[str, Any]) -> None:
        if self.bus is not None:
            self.bus.publish(topic, payload, source="voice")

    def publish_wake(self, word: str) -> None:
        self._publish("input.voice.wake", {"word": word})

    def publish_listening(self, active: bool, until: float) -> None:
        self._publish("input.voice.listening", {"active": active, "until": until})

    def publish_transcript(
        self, text: str, *, raw: str, addressed: bool, final: bool = True
    ) -> None:
        self._publish(
            "input.voice.transcript",
            {"text": text, "final": final, "lang": self.language,
             "addressed": addressed, "raw": raw},
        )

    def _make_stream_factory(self) -> Callable[..., Any]:
        if self._stream_factory is not None:
            return self._stream_factory
        import sounddevice

        return sounddevice.InputStream

    def _input_device(self) -> int | str | None:
        wanted = self.config.input_device.strip().lower()
        if not wanted:
            return None
        import sounddevice

        for index, device in enumerate(sounddevice.query_devices()):
            if wanted in str(device.get("name", "")).lower() and int(device.get("max_input_channels", 0)) > 0:
                return index
        raise RuntimeError(f"No microphone matches voice.input_device={self.config.input_device!r}")

    def _audio_callback(self, indata: np.ndarray, frames: int, timing: Any, status: Any) -> None:
        del frames, timing, status
        if self.echo_guard:
            return
        block = np.asarray(indata[:, 0], dtype=np.float32).copy()
        if not np.any(block):
            self._all_zero_frames += block.size
        else:
            self._all_zero_frames = 0
        try:
            self._audio_queue.put_nowait(block)
        except queue.Full:
            try:
                self._audio_queue.get_nowait()
            except queue.Empty:
                pass
            self._dropped_blocks += 1
            try:
                self._audio_queue.put_nowait(block)
            except queue.Full:
                self._dropped_blocks += 1

    def _ensure_transcriber(self) -> Transcriber:
        if self._transcriber is None:
            self._transcriber = self._transcriber_factory(
                self.config.stt_backend, self.config.stt_model,
                allow_cloud=self.config.allow_cloud_stt,
            )
            _LOG.info("Voice STT backend selected: %s", self._transcriber.name)
        return self._transcriber

    def _expire_window(self) -> None:
        if self._active_until and self._clock() >= self._active_until:
            self._active_until = 0.0
            self.publish_listening(False, 0.0)

    def _handle_segment(self, segment: Segment) -> None:
        try:
            transcriber = self._ensure_transcriber()
            raw = transcriber.transcribe(segment.audio, self.language).strip()
        except Exception as exc:
            _LOG.warning("Local speech transcription unavailable: %s", type(exc).__name__)
            self._publish("system.error", {
                "where": "voice.stt", "error": "speech recognition unavailable",
                "detail": str(exc)[:300],
            })
            return
        self._last_stt_activity = self._clock()
        rms = float(np.sqrt(np.mean(np.square(segment.audio, dtype=np.float64))))
        if is_hallucination(raw, rms=rms, threshold=self.config.vad_threshold):
            return
        command = self._wake.check(raw)
        now = self._clock()
        addressed = command is not None or now < self._active_until
        if command is not None:
            wake_word = raw[: max(1, len(raw) - len(command))].strip(" ,.!?")
            self.publish_wake(wake_word or self.config.wake_words[0])
            self._active_until = now + self.config.listen_seconds
            self.publish_listening(True, self._wall_clock() + self.config.listen_seconds)
            command_text = command
        else:
            command_text = raw if addressed else ""
        self.publish_transcript(command_text if addressed else raw, raw=raw, addressed=addressed)
        if addressed and command_text.strip():
            self.execute(command_text.strip())

    def _process_audio(self) -> None:
        last_audio = self._clock()
        while not self._stop.is_set():
            self._expire_window()
            try:
                block = self._audio_queue.get(timeout=0.2)
                last_audio = self._clock()
            except queue.Empty:
                if self._transcriber is not None and (
                    self._clock() - self._last_stt_activity >= self.config.stt_idle_unload_s
                ):
                    self._transcriber.close()
                    self._transcriber = None
                    self._last_stt_activity = self._clock()
                continue
            if self._all_zero_frames >= 3 * _SAMPLE_RATE:
                now = self._clock()
                if now - self._last_zero_notice >= 10:
                    self._last_zero_notice = now
                    self._publish("system.error", {
                        "where": "voice.microphone",
                        "error": "Microphone returned only silent samples",
                        "detail": "System Settings > Privacy & Security > Microphone: enable <host app>",
                    })
                self._all_zero_frames = 0
                continue
            for segment in self._vad.feed(block):
                self._handle_segment(segment)
            if self._dropped_blocks and self._dropped_blocks % 50 == 0:
                _LOG.warning("Voice input queue dropped %d audio blocks", self._dropped_blocks)
        del last_audio

    def _capture(self) -> None:
        retry_window = 0.0
        while not self._stop.is_set():
            try:
                factory = self._make_stream_factory()
                device = self._input_device()
                with factory(
                    samplerate=_SAMPLE_RATE, channels=1, dtype="float32",
                    blocksize=_BLOCK_SIZE, device=device, callback=self._audio_callback,
                ):
                    _LOG.info("Microphone stream opened (device=%s)", device if device is not None else "system default")
                    retry_window = 0.0
                    while not self._stop.wait(0.2):
                        pass
            except Exception as exc:
                retry_window += 10.0
                self._publish("system.error", {
                    "where": "voice.microphone",
                    "error": "Microphone unavailable",
                    "detail": "System Settings > Privacy & Security > Microphone: enable <host app>",
                })
                _LOG.warning("Microphone stream unavailable: %s", type(exc).__name__)
                if retry_window >= 60.0:
                    _LOG.error("Microphone retry window exhausted; voice capture disabled")
                    return
                self._stop.wait(10.0)

    def start(self) -> None:
        if self._thread is not None or not self.config.enabled:
            return
        if self.config.stt_backend == "google" and not self.config.allow_cloud_stt:
            _LOG.error("Google STT requested but voice.allow_cloud_stt is false")
            self._publish("system.error", {
                "where": "voice.stt", "error": "Cloud STT is disabled",
                "detail": "Set voice.allow_cloud_stt=true to allow audio to leave this Mac.",
            })
            return
        if self.config.debug_save_audio:
            _LOG.warning("voice.debug_save_audio is enabled; utterance audio will be saved locally")
        if self._speaker is not None:
            self._speaker.start()
            self.bus and self.bus.publish(
                "tts.say",
                {"text": f"Listening for your command for {self.config.listen_seconds} seconds.", "interrupt": True},
                source="voice",
            )
        self._thread = threading.Thread(target=self._process_audio, name="pie-voice", daemon=True)
        self._thread.start()
        capture = threading.Thread(target=self._capture, name="pie-microphone", daemon=True)
        capture.start()
        self._capture_thread = capture

    def stop(self) -> None:
        self._stop.set()
        if hasattr(self, "_capture_thread"):
            self._capture_thread.join(timeout=2)
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None
        if self._transcriber is not None:
            self._transcriber.close()
            self._transcriber = None
        if self._speaker is not None:
            self._speaker.stop()
        self.publish_listening(False, 0.0)


__all__ = ["VoiceController"]
