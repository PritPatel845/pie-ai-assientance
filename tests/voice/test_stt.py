from __future__ import annotations

from pathlib import Path

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
    assert len(calls) == 1
    adapter.close()


def test_mlx_adapter_rejects_unknown_model(tmp_path: Path) -> None:
    adapter = MlxWhisperTranscriber("unknown", cache_dir=tmp_path)
    with pytest.raises(ValueError, match="Unsupported"):
        adapter.transcribe(np.zeros(100, dtype=np.float32), "en")
