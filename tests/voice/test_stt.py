from __future__ import annotations

import importlib
from pathlib import Path
from types import ModuleType

import numpy as np
import pytest

from pie.inputs.voice.stt import MlxWhisperTranscriber, is_hallucination


@pytest.mark.parametrize(
    ("text", "rms", "expected"),
    [
        ("", 0.0, True),
        ("...", 0.0, True),
        ("thank you.", 0.001, True),
        ("you", 0.001, True),
        ("[BLANK_AUDIO]", 0.001, True),
        ("go go go go", 0.001, True),
        ("hello there", 0.001, False),
        ("thank you.", 0.04, False),
        ("open safari", 0.02, False),
    ],
)
def test_hallucination_filter(text: str, rms: float, expected: bool) -> None:
    assert is_hallucination(text, rms=rms, threshold=0.015) is expected


def test_mlx_adapter_downloads_lazily_and_returns_text(tmp_path: Path) -> None:
    model_dir = tmp_path / "downloaded-model"
    model_dir.mkdir()
    calls: list[dict[str, object]] = []

    def download(**kwargs: object) -> str:
        calls.append(kwargs)
        return str(model_dir)

    def transcribe(audio: np.ndarray, **kwargs: object) -> dict[str, str]:
        assert audio.dtype == np.float32
        assert kwargs["path_or_hf_repo"] == str(model_dir)
        return {"text": " open Safari "}

    adapter = MlxWhisperTranscriber(
        cache_dir=tmp_path / "cache",
        downloader=download,
        transcribe_fn=transcribe,
    )
    assert calls == []
    result = adapter.transcribe(np.ones(1600, dtype=np.float32), "en")
    assert result == "open Safari"
    assert calls == [
        {
            "repo_id": "mlx-community/whisper-base.en-mlx",
            "cache_dir": str(tmp_path / "cache"),
            "local_files_only": True,
        }
    ]
    adapter.close()


def test_mlx_adapter_falls_back_to_download_only_when_cache_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model_dir = tmp_path / "downloaded-model"
    model_dir.mkdir()
    calls: list[dict[str, object]] = []

    class LocalEntryNotFoundError(Exception):
        pass

    hub_errors = ModuleType("huggingface_hub.errors")
    hub_errors.LocalEntryNotFoundError = LocalEntryNotFoundError  # type: ignore[attr-defined]
    original_import_module = importlib.import_module

    def import_module(name: str, package: str | None = None) -> ModuleType:
        if name == "huggingface_hub.errors":
            return hub_errors
        return original_import_module(name, package)

    monkeypatch.setattr("pie.inputs.voice.stt.importlib.import_module", import_module)

    def download(**kwargs: object) -> str:
        calls.append(kwargs)
        if kwargs.get("local_files_only") is True:
            raise LocalEntryNotFoundError("no local snapshot")
        return str(model_dir)

    adapter = MlxWhisperTranscriber(cache_dir=tmp_path / "cache", downloader=download)
    assert adapter._ensure_model() == model_dir
    assert calls == [
        {
            "repo_id": "mlx-community/whisper-base.en-mlx",
            "cache_dir": str(tmp_path / "cache"),
            "local_files_only": True,
        },
        {
            "repo_id": "mlx-community/whisper-base.en-mlx",
            "cache_dir": str(tmp_path / "cache"),
        },
    ]


def test_mlx_adapter_rejects_unknown_model(tmp_path: Path) -> None:
    adapter = MlxWhisperTranscriber("unknown", cache_dir=tmp_path)
    with pytest.raises(ValueError, match="Unsupported"):
        adapter.transcribe(np.zeros(100, dtype=np.float32), "en")


def test_pipeline_uses_one_dedicated_stt_worker() -> None:
    import threading

    from pie.config import VoiceConfig
    from pie.inputs.voice.pipeline import VoiceController
    from pie.inputs.voice.vad import Segment

    completed = threading.Event()
    worker_names: list[str] = []

    class FakeTranscriber:
        name = "fake"

        def transcribe(self, audio: np.ndarray, language: str) -> str:
            worker_names.append(threading.current_thread().name)
            completed.set()
            return ""

        def close(self) -> None:
            return None

    controller = VoiceController(
        object(),
        config=VoiceConfig(enabled=True, tts_enabled=False, stt_idle_unload_s=300),
        transcriber_factory=lambda *args, **kwargs: FakeTranscriber(),
    )
    controller._stt_thread = threading.Thread(
        target=controller._process_stt, name="pie-stt", daemon=True
    )
    controller._stt_thread.start()
    controller._stt_queue.put(
        Segment(np.ones(1600, dtype=np.float32), started_at=0.0, ended_at=0.1)
    )
    assert completed.wait(1)
    controller._stop.set()
    controller._stt_thread.join(timeout=1)
    assert worker_names == ["pie-stt"]


def test_mlx_adapter_rejects_oversized_cached_model(tmp_path: Path) -> None:
    model_dir = tmp_path / "base.en"
    model_dir.mkdir()
    with (model_dir / "oversized.bin").open("wb") as handle:
        handle.truncate(1_000_000_001)
    adapter = MlxWhisperTranscriber(cache_dir=tmp_path)
    with pytest.raises(RuntimeError, match="1 GB"):
        adapter.transcribe(np.zeros(1600, dtype=np.float32), "en")
