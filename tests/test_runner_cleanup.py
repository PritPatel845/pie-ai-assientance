"""Camera runner setup, processing, and unconditional cleanup
follow Phase 0S §3.8 (PDF pp. 22–23)."""

from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

import pie.inputs.gesture.runner as runner


class Capture:
    def __init__(self):
        self.released = False

    def isOpened(self):
        return True

    def read(self):
        raise RuntimeError("synthetic capture failure")

    def release(self):
        self.released = True


class LandmarkerContext:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def test_runner_releases_camera_and_learning_on_failure(monkeypatch, tmp_path) -> None:
    capture = Capture()
    closed = []
    cv2 = SimpleNamespace(destroyAllWindows=lambda: closed.append("windows"))
    landmarker = SimpleNamespace(create_from_options=lambda _options: LandmarkerContext())
    vision = SimpleNamespace(
        HandLandmarkerOptions=lambda **_kwargs: object(),
        RunningMode=SimpleNamespace(VIDEO="VIDEO"),
        HandLandmarker=landmarker,
    )
    mediapipe = SimpleNamespace(
        tasks=SimpleNamespace(BaseOptions=lambda **_kwargs: object(), vision=vision)
    )

    class FakeLearning:
        def __init__(self, _path):
            pass

        def close(self):
            closed.append("learning")

    monkeypatch.setitem(sys.modules, "cv2", cv2)
    monkeypatch.setitem(sys.modules, "mediapipe", mediapipe)
    monkeypatch.setattr(runner, "ensure_model", lambda _path: tmp_path / "model.task")
    monkeypatch.setattr(runner, "LearningEngine", FakeLearning)

    with pytest.raises(RuntimeError, match="synthetic capture failure"):
        runner.run(
            no_actions=True,
            preview=False,
            model_path="unused",
            capture_factory=lambda _camera: capture,
            learning_dir=tmp_path,
        )
    assert capture.released
    assert closed == ["learning", "windows"]


def test_runner_releases_camera_if_model_options_fail(monkeypatch, tmp_path) -> None:
    capture = Capture()
    closed = []
    cv2 = SimpleNamespace(destroyAllWindows=lambda: closed.append("windows"))

    def fail_options(**_kwargs):
        raise RuntimeError("synthetic model setup failure")

    vision = SimpleNamespace(
        HandLandmarkerOptions=fail_options,
        RunningMode=SimpleNamespace(VIDEO="VIDEO"),
        HandLandmarker=SimpleNamespace(),
    )
    mediapipe = SimpleNamespace(
        tasks=SimpleNamespace(BaseOptions=lambda **_kwargs: object(), vision=vision)
    )
    monkeypatch.setitem(sys.modules, "cv2", cv2)
    monkeypatch.setitem(sys.modules, "mediapipe", mediapipe)
    monkeypatch.setattr(runner, "ensure_model", lambda _path: tmp_path / "model.task")

    with pytest.raises(RuntimeError, match="synthetic model setup failure"):
        runner.run(
            no_actions=True,
            preview=False,
            model_path="unused",
            capture_factory=lambda _camera: capture,
            learning_dir=tmp_path,
        )
    assert capture.released
    assert closed == ["windows"]


def test_runner_releases_camera_if_controller_setup_fails(monkeypatch, tmp_path) -> None:
    capture = Capture()
    closed = []
    cv2 = SimpleNamespace(destroyAllWindows=lambda: closed.append("windows"))
    vision = SimpleNamespace(
        HandLandmarkerOptions=lambda **_kwargs: object(),
        RunningMode=SimpleNamespace(VIDEO="VIDEO"),
        HandLandmarker=SimpleNamespace(),
    )
    mediapipe = SimpleNamespace(
        tasks=SimpleNamespace(BaseOptions=lambda **_kwargs: object(), vision=vision)
    )
    monkeypatch.setitem(sys.modules, "cv2", cv2)
    monkeypatch.setitem(sys.modules, "mediapipe", mediapipe)
    monkeypatch.setattr(runner, "ensure_model", lambda _path: tmp_path / "model.task")

    def fail_controller():
        raise RuntimeError("synthetic controller setup failure")

    monkeypatch.setattr(runner, "MacController", fail_controller)
    with pytest.raises(RuntimeError, match="synthetic controller setup failure"):
        runner.run(
            no_actions=True,
            preview=False,
            model_path="unused",
            capture_factory=lambda _camera: capture,
            learning_dir=tmp_path,
        )
    assert capture.released
    assert closed == ["windows"]
