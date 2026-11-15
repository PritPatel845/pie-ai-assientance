from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from pie.inputs.gesture import engine


class FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.reads = 0

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self, size: int = -1) -> bytes:
        del size
        self.reads += 1
        return self.payload if self.reads == 1 else b""


def test_resolve_model_path_checks_size_and_sha256(tmp_path: Path, monkeypatch) -> None:
    payload = b"trusted model bytes"
    monkeypatch.setattr(engine, "MODEL_BYTES", len(payload))
    monkeypatch.setattr(engine, "MODEL_SHA256", hashlib.sha256(payload).hexdigest())
    model = tmp_path / "hand_landmarker.task"
    model.write_bytes(payload)
    assert engine.resolve_model_path(model) == model
    model.write_bytes(b"tampered model data")
    assert engine.resolve_model_path(model) is None


def test_explicit_download_verifies_model_before_install(tmp_path: Path, monkeypatch) -> None:
    payload = b"known-good-model"
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(engine, "MODEL_BYTES", len(payload))
    monkeypatch.setattr(engine, "MODEL_SHA256", hashlib.sha256(payload).hexdigest())
    monkeypatch.setattr(engine.urllib.request, "urlopen", lambda *args, **kwargs: FakeResponse(payload))
    result = engine.ensure_model(download=True)
    assert result == tmp_path / ".pie" / "models" / "hand_landmarker.task"
    assert result.read_bytes() == payload


def test_bad_download_is_removed_and_rejected(tmp_path: Path, monkeypatch) -> None:
    payload = b"wrong-model"
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(engine, "MODEL_BYTES", len(payload))
    monkeypatch.setattr(engine, "MODEL_SHA256", "0" * 64)
    monkeypatch.setattr(engine.urllib.request, "urlopen", lambda *args, **kwargs: FakeResponse(payload))
    with pytest.raises(ValueError, match="SHA-256"):
        engine.ensure_model(download=True)
    assert not (tmp_path / ".pie" / "models" / "hand_landmarker.task").exists()
    assert not (tmp_path / ".pie" / "models" / "hand_landmarker.task.tmp").exists()
