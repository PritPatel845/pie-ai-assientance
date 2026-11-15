from __future__ import annotations

import importlib
import importlib.util
import logging
import re
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Any, Protocol

import numpy as np
from numpy.typing import NDArray

_LOG = logging.getLogger(__name__)
Audio = NDArray[np.float32]
_MODEL_REPOS = {"base.en": "mlx-community/whisper-base.en-mlx"}
_MAX_MODEL_BYTES = 1_000_000_000


class Transcriber(Protocol):
    name: str

    def transcribe(self, audio: Audio, language: str) -> str: ...
    def close(self) -> None: ...


def is_hallucination(text: str, *, rms: float, threshold: float) -> bool:
    cleaned = text.strip()
    if not cleaned or not re.search(r"[\w]", cleaned):
        return True
    normalized = re.sub(r"[^\w']+", " ", cleaned.lower()).split()
    if rms >= threshold * 2:
        return False
    if cleaned.lower() in {"thank you.", "thank you", "you", "[blank_audio]"}:
        return True
    return len(normalized) >= 4 and len(set(normalized)) == 1


class MlxWhisperTranscriber:
    """Lazy MLX Whisper adapter; model snapshots live inside ~/.pie/models/stt."""

    name = "mlx-whisper"

    def __init__(
        self,
        model: str = "base.en",
        *,
        cache_dir: Path | None = None,
        transcribe_fn: Any | None = None,
        downloader: Any | None = None,
    ) -> None:
        self.model = model
        self.cache_dir = cache_dir or Path.home() / ".pie" / "models" / "stt"
        self._transcribe_fn = transcribe_fn
        self._downloader = downloader
        self._model_path: Path | None = None
        self._lock = threading.Lock()

    def _ensure_model(self) -> Path:
        if self._model_path is not None and self._model_path.is_dir():
            return self._model_path
        repo_id = _MODEL_REPOS.get(self.model)
        if repo_id is None:
            raise ValueError(f"Unsupported MLX Whisper model: {self.model}")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        target = self.cache_dir / self.model
        if target.is_dir() and any(target.iterdir()):
            self._model_path = target
            return target
        _LOG.info("Downloading local speech model %s to %s", self.model, target)
        downloader = self._downloader
        if downloader is None:
            hub = importlib.import_module("huggingface_hub")
            downloader = hub.snapshot_download
        downloaded = downloader(repo_id=repo_id, cache_dir=str(self.cache_dir))
        self._model_path = Path(downloaded)
        model_bytes = sum(
            item.stat().st_size for item in self._model_path.rglob("*") if item.is_file()
        )
        if model_bytes > _MAX_MODEL_BYTES:
            self._model_path = None
            raise RuntimeError(
                f"Speech model exceeds the 1 GB memory/disk budget ({model_bytes} bytes)"
            )
        _LOG.info(
            "Speech model %s is ready (%.1f MB on disk)",
            self.model,
            model_bytes / 1_000_000,
        )
        return self._model_path

    def transcribe(self, audio: Audio, language: str) -> str:
        with self._lock:
            model_path = self._ensure_model()
            transcribe_fn = self._transcribe_fn
            if transcribe_fn is None:
                module = importlib.import_module("mlx_whisper")
                transcribe_fn = module.transcribe
                self._transcribe_fn = transcribe_fn
            result = transcribe_fn(
                np.asarray(audio, dtype=np.float32),
                path_or_hf_repo=str(model_path),
                language=language,
                verbose=False,
            )
        if isinstance(result, dict):
            return str(result.get("text", "")).strip()
        return str(result).strip()

    def close(self) -> None:
        # MLX releases model buffers when references are dropped.
        self._model_path = None
        self._transcribe_fn = None


class WhisperCppTranscriber:
    """Optional whisper.cpp CLI adapter; never invokes a shell."""

    name = "whisper.cpp"

    def __init__(self, model_path: Path, executable: str | None = None) -> None:
        self.model_path = model_path
        self.executable = (
            executable or shutil.which("whisper-cli") or shutil.which("whisper-cpp") or ""
        )
        if not self.executable:
            raise RuntimeError("whisper.cpp CLI not found (install whisper-cpp with Homebrew)")

    def transcribe(self, audio: Audio, language: str) -> str:
        import tempfile
        import wave

        self.model_path = self.model_path.expanduser()
        if not self.model_path.is_file():
            raise RuntimeError(f"whisper.cpp model is missing: {self.model_path}")
        with tempfile.TemporaryDirectory(prefix="pie-stt-") as directory:
            wav_path = Path(directory) / "utterance.wav"
            pcm = np.clip(audio, -1.0, 1.0)
            pcm16 = (pcm * 32767).astype("<i2")
            with wave.open(str(wav_path), "wb") as handle:
                handle.setnchannels(1)
                handle.setsampwidth(2)
                handle.setframerate(16_000)
                handle.writeframes(pcm16.tobytes())
            result = subprocess.run(
                [
                    self.executable,
                    "-m",
                    str(self.model_path),
                    "-f",
                    str(wav_path),
                    "-l",
                    language,
                    "--no-timestamps",
                ],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
                shell=False,
            )
            if result.returncode != 0:
                raise RuntimeError(f"whisper.cpp failed: {result.stderr[-500:]}")
            return result.stdout.strip()

    def close(self) -> None:
        return None


def create_transcriber(backend: str, model: str, *, allow_cloud: bool = False) -> Transcriber:
    if backend == "google":
        if not allow_cloud:
            raise RuntimeError("Google speech recognition requires voice.allow_cloud_stt=true")
        raise RuntimeError("Google speech recognition adapter is not installed in this build")
    if backend in {"auto", "mlx"}:
        if importlib.util.find_spec("mlx_whisper") is not None:
            return MlxWhisperTranscriber(model)
        if backend == "mlx":
            raise RuntimeError("mlx-whisper is not installed; install the macOS STT extra")
    if backend in {"auto", "whispercpp"}:
        model_path = Path.home() / ".pie" / "models" / "stt" / "ggml-base.en.bin"
        return WhisperCppTranscriber(model_path)
    raise RuntimeError(f"No supported speech backend available: {backend}")
