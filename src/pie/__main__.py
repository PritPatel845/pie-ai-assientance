from __future__ import annotations

import argparse
import importlib
import json
import platform
import sys
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

from pie import __version__
from pie.brain.module import BrainModule
from pie.config import Config, load_config
from pie.core.daemon import Daemon
from pie.events import Event
from pie.inputs.gesture.engine import resolve_model_path
from pie.inputs.gesture.runner import run
from pie.inputs.voice.pipeline import VoiceController
from pie.logging_setup import configure_logging
from pie.paths import learning_dir, logs_dir, models_dir, pie_home, state_dir
from pie.platform.mac import MacController


class GestureModule:
    name = "gesture"

    def start(self, daemon: Daemon) -> None:
        self.daemon = daemon

    def stop(self) -> None:
        return None


class VoiceModule:
    name = "voice"

    def __init__(self, *, no_actions: bool = False) -> None:
        self.no_actions = no_actions
        self.controller: VoiceController | None = None

    def start(self, daemon: Daemon) -> None:
        self.controller = VoiceController(
            MacController(),
            no_actions=self.no_actions,
            bus=daemon.bus,
            config=daemon.config.voice,
        )
        self.controller.start()

    def stop(self) -> None:
        if self.controller is not None:
            self.controller.stop()


def _truncate(value: Any) -> Any:
    if isinstance(value, str):
        return value if len(value) <= 200 else value[:197] + "..."
    if isinstance(value, dict):
        return {key: _truncate(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_truncate(item) for item in value]
    if isinstance(value, tuple):
        return [_truncate(item) for item in value]
    return value


def _print_event(event: Event) -> None:
    print(json.dumps(_truncate(asdict(event)), ensure_ascii=False, default=str), flush=True)


def doctor() -> int:
    print(f"Pie {__version__}")
    print(f"Python: {sys.version.split()[0]} ({sys.executable})")
    print(f"Platform: {platform.platform()}")
    for module in ("cv2", "numpy", "mediapipe", "pyautogui", "Quartz", "AppKit"):
        try:
            loaded = importlib.import_module(module)
            print(f"{module}: OK ({getattr(loaded, '__version__', 'installed')})")
        except Exception as exc:
            print(f"{module}: FAIL ({type(exc).__name__}: {exc})")
    model = resolve_model_path()
    print(f"Hand model: {model if model else 'NOT FOUND'}")
    for path in (pie_home(), state_dir(), logs_dir(), models_dir(), learning_dir()):
        print(f"{path}: {'exists' if path.exists() else 'not created'}")
    legacy_learning = Path.home() / ".jarvis_learning"
    legacy_status = "found" if legacy_learning.is_dir() else "not found"
    print(f"Legacy learning folder: {legacy_status}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pie",
        description="Pie hand-gesture and voice assistant",
    )
    parser.add_argument("--version", action="version", version=f"Pie {__version__}")
    parser.add_argument("--camera", type=int, default=None)
    parser.add_argument(
        "--no-actions",
        action="store_true",
        help="Preview and classify without OS actions",
    )
    parser.add_argument(
        "--game-profile",
        choices=("asphalt", "temple-run", "counter-strike"),
        default="asphalt",
    )
    parser.add_argument("--steer-sensitivity", type=float, default=None)
    voice = parser.add_mutually_exclusive_group()
    voice.add_argument("--voice", dest="voice", action="store_true", default=None)
    voice.add_argument("--no-voice", dest="voice", action="store_false", default=None)
    parser.add_argument("--voice-background", action="store_true")
    parser.add_argument("--learning-dir", type=Path)
    parser.add_argument("--voice-listen-seconds", type=int, default=None)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--download-model", action="store_true")
    parser.add_argument(
        "--print-events",
        action="store_true",
        help="Print each event as one JSON line",
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=("run", "doctor", "config", "brain"),
        default="run",
    )
    parser.add_argument("config_action", nargs="?")
    parser.add_argument("brain_args", nargs="*")
    return parser


def _effective_config(args: argparse.Namespace) -> Config:
    config = load_config(args.config)
    gesture = replace(
        config.gesture,
        camera=args.camera if args.camera is not None else config.gesture.camera,
        steer_sensitivity=(
            args.steer_sensitivity
            if args.steer_sensitivity is not None
            else config.gesture.steer_sensitivity
        ),
    )
    voice = replace(
        config.voice,
        enabled=args.voice if args.voice is not None else config.voice.enabled,
        listen_seconds=(
            args.voice_listen_seconds
            if args.voice_listen_seconds is not None
            else config.voice.listen_seconds
        ),
    )
    return replace(config, gesture=gesture, voice=voice)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "doctor":
        return doctor()
    if args.command == "brain":
        from pie.brain.cli import run_brain_command

        try:
            return run_brain_command(args.config_action, args.brain_args, args.config)
        except (OSError, RuntimeError, ValueError) as exc:
            parser.error(str(exc))
    try:
        config = _effective_config(args)
        if args.command == "config":
            if args.config_action != "show":
                parser.error("use: pie config show")
            print(json.dumps(asdict(config), indent=2, ensure_ascii=False))
            return 0
        if args.download_model:
            from pie.inputs.gesture.engine import ensure_model

            model_file = ensure_model(config.gesture.model_path or None, download=True)
            print(f"Hand model ready: {model_file}")
            return 0
        configure_logging(config.app.log_level)
        daemon = Daemon(config)
        if not args.voice_background:
            daemon.register_module(GestureModule())
        if config.voice.enabled:
            daemon.register_module(VoiceModule(no_actions=args.no_actions))
        if config.brain.enabled:
            daemon.register_module(BrainModule())

        def main_thread() -> None:
            if args.print_events and daemon.bus is not None:
                daemon.bus.subscribe("*", _print_event, name="stdout")
            if args.voice_background:
                daemon.stop_flag.wait()
                return
            run(
                camera=config.gesture.camera,
                no_actions=args.no_actions,
                game_profile=args.game_profile,
                steer_sensitivity=config.gesture.steer_sensitivity,
                arm_hold_seconds=config.gesture.arm_hold_seconds,
                model_path=config.gesture.model_path,
                preview=config.gesture.preview,
                learning_dir=args.learning_dir,
                bus=daemon.bus,
                stop=daemon.stop_flag,
                state_hz=config.gesture.state_hz,
            )

        daemon.run_main(main_thread)
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
