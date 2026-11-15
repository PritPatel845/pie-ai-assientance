from __future__ import annotations

import importlib
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, Literal, Protocol

from pie.inputs.gesture.engine import ensure_model
from pie.inputs.gesture.features import Landmark
from pie.inputs.gesture.frame import (
    Action,
    DoubleClick,
    FrameProcessor,
    FrameResult,
    KeyAction,
    MouseClick,
    MoveCursor,
    Mute,
    PlayMedia,
    RunVoiceCommand,
    Scroll,
    SetVolume,
    StopMedia,
    Tap,
)
from pie.inputs.gesture.learning import LearningEngine
from pie.platform.mac import MacController


class Capture(Protocol):
    def isOpened(self) -> bool: ...
    def read(self) -> tuple[bool, Any]: ...
    def release(self) -> None: ...


class ActionSink:
    """Translate pure FrameProcessor actions into an injectable platform adapter."""

    def __init__(
        self, controller: MacController, *, no_actions: bool = False, profile: str = "asphalt"
    ) -> None:
        self.controller, self.no_actions, self.profile = controller, no_actions, profile

    def execute(self, action: Action) -> None:
        if self.no_actions:
            return
        if isinstance(action, MoveCursor):
            self.controller.move_cursor(action.x, action.y)
        elif isinstance(action, DoubleClick):
            self.controller.double_click()
        elif isinstance(action, Mute):
            self.controller.mute()
        elif isinstance(action, PlayMedia):
            self.controller.play_media()
        elif isinstance(action, StopMedia):
            self.controller.stop_media()
        elif isinstance(action, RunVoiceCommand):
            self.controller.run_voice_command()
        elif isinstance(action, Scroll):
            self.controller.scroll(action.amount)
        elif isinstance(action, SetVolume):
            self.controller.set_volume(action.value)
        elif isinstance(action, KeyAction):
            from pie.inputs.gesture.game import GAME_PROFILES, MAC_KEY_CODES

            profile_key = GAME_PROFILES[self.profile].get(action.name, action.name)
            key = {"accelerate": "up", "brake": "down", "slide": "down"}.get(
                profile_key, profile_key
            )
            self.controller.key_event(MAC_KEY_CODES[key], action.pressed)
        elif isinstance(action, Tap):
            from pie.inputs.gesture.game import GAME_PROFILES, MAC_KEY_CODES

            key = GAME_PROFILES[self.profile].get(action.name, action.name)
            self.controller.key_event(MAC_KEY_CODES[key], True)
            self.controller.key_event(MAC_KEY_CODES[key], False)
        elif isinstance(action, MouseClick):
            self.controller.mouse_click()


def draw_hand(frame: Any, landmarks: Sequence[Landmark], cv2: Any) -> None:
    height, width = frame.shape[:2]
    points = [(int(p.x * width), int(p.y * height)) for p in landmarks]
    for start, end in (
        (0, 1),
        (1, 2),
        (2, 3),
        (3, 4),
        (0, 5),
        (5, 6),
        (6, 7),
        (7, 8),
        (5, 9),
        (9, 10),
        (10, 11),
        (11, 12),
        (9, 13),
        (13, 14),
        (14, 15),
        (15, 16),
        (13, 17),
        (17, 18),
        (18, 19),
        (19, 20),
        (0, 17),
    ):
        cv2.line(frame, points[start], points[end], (80, 220, 180), 2)
    for point in points:
        cv2.circle(frame, point, 4, (245, 190, 100), -1)


def draw_hud(frame: Any, result: FrameResult, fps: float, cv2: Any, *, no_actions: bool) -> None:
    status = "DISABLED" if no_actions else ("ARMED" if result.armed else "WAITING TO ARM")
    lines = [
        f"PIE | {result.gesture}",
        f"MODE STATUS: {status}",
        f"DEPTH: {result.depth if result.depth is not None else '--'}",
        f"VOLUME: {result.volume if result.volume is not None else '--'}",
        f"FPS: {fps:.1f}",
        "HOLD OPEN PALM TO ARM | G: desktop/game | Q: quit",
    ]
    for index, line in enumerate(lines):
        cv2.putText(
            frame,
            line,
            (12, 24 + index * 23),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.52,
            (136, 232, 208),
            1,
            cv2.LINE_AA,
        )


def run(
    *,
    camera: int = 0,
    no_actions: bool = False,
    game_profile: str = "asphalt",
    steer_sensitivity: float = 0.004,
    arm_hold_seconds: float = 2.0,
    model_path: str = "",
    preview: bool = True,
    learning_dir: Path | None = None,
    capture_factory: Callable[[int], Capture] | None = None,
) -> None:
    try:
        cv2 = importlib.import_module("cv2")
        mp = importlib.import_module("mediapipe")
    except ImportError as exc:
        raise RuntimeError("Install Pie with the [mac] extra to run camera tracking") from exc

    model = ensure_model(model_path or None)
    capture = (capture_factory or cv2.VideoCapture)(camera)
    if not capture.isOpened():
        capture.release()
        raise RuntimeError(
            f"Could not open camera {camera}. Try --camera 1 or check Camera permission."
        )
    processor: FrameProcessor | None = None
    sink: ActionSink | None = None
    learning: LearningEngine | None = None
    try:
        options = mp.tasks.vision.HandLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(model)),
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_hands=2,
            min_hand_detection_confidence=0.6,
            min_hand_presence_confidence=0.6,
            min_tracking_confidence=0.5,
        )
        controller = MacController()
        sink = ActionSink(controller, no_actions=no_actions, profile=game_profile)
        processor = FrameProcessor(
            arm_hold_seconds=arm_hold_seconds, steer_sensitivity=steer_sensitivity
        )
        learning = LearningEngine(learning_dir)
        previous_time = time.monotonic()
        fps = 0.0
        with mp.tasks.vision.HandLandmarker.create_from_options(options) as landmarker:
            while True:
                ok, frame = capture.read()
                if not ok:
                    break
                frame = cv2.flip(frame, 1)
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                timestamp_ms = int(time.monotonic() * 1000)
                result = landmarker.detect_for_video(image, timestamp_ms)
                hands = result.hand_landmarks or []
                frame_result = processor.process(hands)
                for action in frame_result.actions:
                    sink.execute(action)
                if hands:
                    learning.record_hand_sample(hands[0], frame_result.gesture)
                    draw_hand(frame, hands[0], cv2)
                now = time.monotonic()
                elapsed = now - previous_time
                if elapsed > 0:
                    fps = 0.9 * fps + 0.1 / elapsed if fps else 1.0 / elapsed
                previous_time = now
                if preview:
                    draw_hud(frame, frame_result, fps, cv2, no_actions=no_actions)
                    cv2.namedWindow("Pie Air Control", cv2.WINDOW_NORMAL)
                    cv2.resizeWindow("Pie Air Control", 640, 360)
                    cv2.moveWindow("Pie Air Control", 20, 60)
                    cv2.imshow("Pie Air Control", frame)
                    key = cv2.waitKey(1) & 0xFF
                    if key in (ord("q"), 27):
                        break
                    if key == ord("g"):
                        mode: Literal["desktop", "game"] = (
                            "game" if processor.mode == "desktop" else "desktop"
                        )
                        for action in processor.set_mode(mode):
                            sink.execute(action)
                    if key in (ord("1"), ord("2"), ord("3")):
                        profile = {"1": "asphalt", "2": "temple-run", "3": "counter-strike"}[
                            chr(key)
                        ]
                        for action in processor.set_mode("game", profile):
                            sink.execute(action)
    finally:
        try:
            if processor is not None and sink is not None:
                for action in processor.reset():
                    sink.execute(action)
        finally:
            try:
                capture.release()
            finally:
                try:
                    if learning is not None:
                        learning.close()
                finally:
                    cv2.destroyAllWindows()
