from __future__ import annotations

import importlib
import logging
import queue
import re
import threading
import time
import wave
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import numpy as np
from numpy.typing import NDArray

from pie.config import VoiceConfig
from pie.events import Event, EventBus
from pie.inputs.voice.executor import VoiceController as _VoiceController
from pie.inputs.voice.stt import Transcriber, create_transcriber, is_hallucination
from pie.inputs.voice.tts import Speaker
from pie.inputs.voice.vad import EnergyVad, Segment
from pie.inputs.voice.wake import TextWake

_LOG = logging.getLogger(__name__)
_SAMPLE_RATE = 16_000
_BLOCK_SIZE = 512
AudioBlock = NDArray[np.float32]


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
        brain_enabled: bool = False,
    ) -> None:
        super().__init__(
            controller,
            no_actions=no_actions,
            listen_seconds=listen_seconds,
            learning_engine=learning_engine,
        )
        self.bus = bus
        self.config = config or VoiceConfig(listen_seconds=listen_seconds, language=language)
        self.brain_enabled = brain_enabled
        self.language = self.config.language
        self._stream_factory = stream_factory
        self._transcriber_factory = transcriber_factory
        self._clock = clock
        self._wall_clock = wall_clock
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._capture_thread: threading.Thread | None = None
        self._stt_thread: threading.Thread | None = None
        self._audio_queue: queue.Queue[AudioBlock] = queue.Queue(maxsize=200)
        self._stt_queue: queue.Queue[Segment | None] = queue.Queue()
        self._dropped_blocks = 0
        self._speaker = (
            Speaker(
                bus,
                enabled=self.config.tts_enabled,
                voice=self.config.tts_voice,
                rate=self.config.tts_rate,
            )
            if bus is not None
            else None
        )
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
        self._stt_disabled = False
        self._all_zero_frames = 0
        self._mic_permission_missing = threading.Event()
        self._unsubscribe_tool_stop = (
            bus.subscribe("input.voice.listening", self._on_listening_event, name="voice-tool-stop")
            if bus is not None
            else None
        )
        self._unsubscribe_permission_request = (
            bus.subscribe(
                "permission.request",
                self._on_permission_request,
                name="voice-permission-window",
            )
            if bus is not None
            else None
        )

    def _on_listening_event(self, event: Event) -> None:
        if event.source == "tool" and not bool(event.payload.get("active", True)):
            self._active_until = 0.0

    def _on_permission_request(self, event: Event) -> None:
        """Temporarily accept bare yes/no speech only while approval is pending."""
        try:
            timeout_s = float(event.payload.get("timeout_s", self.config.listen_seconds))
        except (TypeError, ValueError):
            timeout_s = float(self.config.listen_seconds)
        timeout_s = min(max(timeout_s, 1.0), 120.0)
        self._active_until = max(self._active_until, self._clock() + timeout_s)
        self.publish_listening(True, self._wall_clock() + timeout_s)

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
        self, text: str, *, raw: str | None = None, addressed: bool = True, final: bool = True
    ) -> None:
        self._publish(
            "input.voice.transcript",
            {
                "text": text,
                "final": final,
                "lang": self.language,
                "addressed": addressed,
                "raw": text if raw is None else raw,
            },
        )

    def _make_stream_factory(self) -> Callable[..., Any]:
        if self._stream_factory is not None:
            return self._stream_factory
        sounddevice = importlib.import_module("sounddevice")

        return cast(Callable[..., Any], sounddevice.InputStream)

    def _input_device(self) -> int | str | None:
        wanted = self.config.input_device.strip().lower()
        if not wanted:
            return None
        sounddevice = importlib.import_module("sounddevice")

        for index, device in enumerate(sounddevice.query_devices()):
            name_matches = wanted in str(device.get("name", "")).lower()
            has_input = int(device.get("max_input_channels", 0)) > 0
            if name_matches and has_input:
                return index
        raise RuntimeError(f"No microphone matches voice.input_device={self.config.input_device!r}")

    def _audio_callback(self, indata: AudioBlock, frames: int, timing: Any, status: Any) -> None:
        del frames, timing, status
        if self.echo_guard:
            return
        block = np.asarray(indata[:, 0], dtype=np.float32).copy()
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
                self.config.stt_backend,
                self.config.stt_model,
                allow_cloud=self.config.allow_cloud_stt,
            )
            _LOG.info("Voice STT backend selected: %s", self._transcriber.name)
        return self._transcriber

    def _expire_window(self) -> None:
        if self._active_until and self._clock() >= self._active_until:
            self._active_until = 0.0
            self.publish_listening(False, 0.0)

    def _save_debug_audio(self, segment: Segment) -> None:
        if not self.config.debug_save_audio:
            return
        directory = Path.home() / ".pie" / "debug_audio"
        directory.mkdir(parents=True, exist_ok=True)
        filename = directory / f"utterance-{datetime.now():%Y%m%d-%H%M%S-%f}.wav"
        pcm = np.clip(segment.audio, -1.0, 1.0)
        with wave.open(str(filename), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(_SAMPLE_RATE)
            handle.writeframes((pcm * 32767).astype("<i2").tobytes())

    def _handle_segment(self, segment: Segment) -> None:
        if self._stt_disabled:
            return
        try:
            self._save_debug_audio(segment)
            transcriber = self._ensure_transcriber()
            raw = transcriber.transcribe(segment.audio, self.language).strip()
        except Exception as exc:
            self._stt_disabled = True
            _LOG.warning(
                "Local speech transcription unavailable; STT disabled: %s", type(exc).__name__
            )
            self._publish(
                "system.error",
                {
                    "where": "voice.stt",
                    "error": "speech recognition unavailable",
                    "detail": str(exc)[:300],
                },
            )
            return
        self._last_stt_activity = self._clock()
        _LOG.debug("Voice transcript: %s", raw)
        rms = float(np.sqrt(np.mean(np.square(segment.audio, dtype=np.float64))))
        if is_hallucination(raw, rms=rms, threshold=self.config.vad_threshold):
            return
        command = self._wake.check(raw)
        now = self._clock()
        permission_window = now < self._active_until
        if command is None and permission_window:
            # Whisper can render the spoken wake word "Pie" as "Bye".
            # Accept only a complete wake-word + yes/no utterance while a
            # confirmation is pending; never search arbitrary sentences for
            # approval keywords.
            match = re.fullmatch(
                r"(?:pie|pi|pai|pye|bye)[,.:;!?\s]+(yes|no)[.!?]*",
                raw.casefold().strip(),
            )
            if match is not None:
                command = match.group(1)
        addressed = command is not None or permission_window
        if command is not None:
            wake_word = raw[: max(1, len(raw) - len(command))].strip(" ,.!?")
            self.publish_wake(wake_word or self.config.wake_words[0])
            self._active_until = now + self.config.listen_seconds
            self.publish_listening(True, self._wall_clock() + self.config.listen_seconds)
            command_text = command
        else:
            command_text = raw if addressed else ""
        self.publish_transcript(command_text if addressed else raw, raw=raw, addressed=addressed)
        if addressed and command_text.strip() and (self.bus is None or not self.brain_enabled):
            self.execute(command_text.strip())

    def _process_audio(self) -> None:
        while not self._stop.is_set():
            self._expire_window()
            try:
                block = self._audio_queue.get(timeout=0.2)
            except queue.Empty:
                continue
            if not np.any(block):
                self._all_zero_frames += block.size
            else:
                self._all_zero_frames = 0
            if self._all_zero_frames >= 3 * _SAMPLE_RATE:
                self._all_zero_frames = 0
                self._mic_permission_missing.set()
                continue
            for segment in self._vad.feed(block):
                self._stt_queue.put_nowait(segment)
            if self._dropped_blocks and self._dropped_blocks % 50 == 0:
                _LOG.warning("Voice input queue dropped %d audio blocks", self._dropped_blocks)

    def _process_stt(self) -> None:
        while not self._stop.is_set():
            try:
                segment = self._stt_queue.get(timeout=0.2)
            except queue.Empty:
                if self._transcriber is not None and (
                    self._clock() - self._last_stt_activity >= self.config.stt_idle_unload_s
                ):
                    self._transcriber.close()
                    self._transcriber = None
                    self._last_stt_activity = self._clock()
                continue
            if segment is None:
                return
            self._handle_segment(segment)
            self._last_stt_activity = self._clock()

    def _capture(self) -> None:
        retry_window = 0.0
        while not self._stop.is_set():
            try:
                factory = self._make_stream_factory()
                device = self._input_device()
                with factory(
                    samplerate=_SAMPLE_RATE,
                    channels=1,
                    dtype="float32",
                    blocksize=_BLOCK_SIZE,
                    device=device,
                    callback=self._audio_callback,
                ):
                    device_name = device if device is not None else "system default"
                    _LOG.info("Microphone stream opened (device=%s)", device_name)
                    retry_window = 0.0
                    while not self._stop.wait(0.2):
                        if self._mic_permission_missing.is_set():
                            self._mic_permission_missing.clear()
                            raise RuntimeError("microphone returned only zero samples")
            except Exception as exc:
                retry_window += 10.0
                self._publish(
                    "system.error",
                    {
                        "where": "voice.microphone",
                        "error": "Microphone unavailable",
                        "detail": (
                            "System Settings > Privacy & Security > Microphone: enable <host app>"
                        ),
                    },
                )
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
            self._publish(
                "system.error",
                {
                    "where": "voice.stt",
                    "error": "Cloud STT is disabled",
                    "detail": "Set voice.allow_cloud_stt=true to allow audio to leave this Mac.",
                },
            )
            return
        if self.config.debug_save_audio:
            _LOG.warning("voice.debug_save_audio is enabled; utterance audio will be saved locally")
        if self.config.stt_backend == "google" and self.config.allow_cloud_stt:
            _LOG.warning("Google speech recognition is enabled; audio will leave this Mac")
        activation = getattr(self.executor.controller, "show_voice_activation", None)
        if callable(activation):
            try:
                activation(self.config.listen_seconds)
            except (OSError, RuntimeError):
                _LOG.warning("Could not display the PIE ACTIVE notification", exc_info=True)
        if self._speaker is not None:
            self._speaker.start()
            self.bus and self.bus.publish(
                "tts.say",
                {
                    "text": (
                        f"Listening for your command for {self.config.listen_seconds} seconds."
                    ),
                    "interrupt": True,
                },
                source="voice",
            )
        self._stt_thread = threading.Thread(target=self._process_stt, name="pie-stt", daemon=True)
        self._stt_thread.start()
        self._thread = threading.Thread(target=self._process_audio, name="pie-voice", daemon=True)
        self._thread.start()
        self._capture_thread = threading.Thread(
            target=self._capture, name="pie-microphone", daemon=True
        )
        self._capture_thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._capture_thread is not None:
            self._capture_thread.join(timeout=2)
            self._capture_thread = None
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None
        if self._stt_thread is not None:
            self._stt_queue.put_nowait(None)
            self._stt_thread.join(timeout=2)
            self._stt_thread = None
        if self._transcriber is not None:
            self._transcriber.close()
            self._transcriber = None
        if self._speaker is not None:
            self._speaker.stop()
        self.publish_listening(False, 0.0)
        if self._unsubscribe_tool_stop is not None:
            self._unsubscribe_tool_stop()
            self._unsubscribe_tool_stop = None
        if self._unsubscribe_permission_request is not None:
            self._unsubscribe_permission_request()
            self._unsubscribe_permission_request = None


__all__ = ["VoiceController"]
