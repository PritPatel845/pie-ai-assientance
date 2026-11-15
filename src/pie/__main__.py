from __future__ import annotations

import argparse
import importlib
import platform
import sys
from pathlib import Path

from pie import __version__
from pie.config import load_config
from pie.inputs.gesture.engine import resolve_model_path
from pie.inputs.gesture.runner import run
from pie.logging_setup import configure_logging
from pie.paths import learning_dir, logs_dir, models_dir, pie_home, state_dir


def doctor() -> int:
    print(f"Pie {__version__}")
    print(f"Python: {sys.version.split()[0]} ({sys.executable})")
    print(f"Platform: {platform.platform()}")
    for module in ("cv2", "numpy", "mediapipe", "pyautogui", "Quartz", "AppKit"):
        try:
            loaded = importlib.import_module(module)
            print(f"{module}: OK ({getattr(loaded, '__version__', 'installed')})")
        except ImportError:
            print(f"{module}: FAIL (not installed)")
    model = resolve_model_path()
    print(f"Hand model: {model if model else 'NOT FOUND'}")
    for path in (pie_home(), state_dir(), logs_dir(), models_dir(), learning_dir()):
        print(f"{path}: {'exists' if path.exists() else 'not created'}")
    print(f"Legacy learning folder: {'found' if (Path.home() / '.jarvis_learning').is_dir() else 'not found'}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pie", description="Pie hand-gesture and voice assistant")
    parser.add_argument("--version", action="version", version=f"Pie {__version__}")
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--no-actions", action="store_true", help="Preview and classify without OS actions")
    parser.add_argument("--game-profile", choices=("asphalt", "temple-run", "counter-strike"),
                        default="asphalt")
    parser.add_argument("--steer-sensitivity", type=float, default=0.004)
    voice = parser.add_mutually_exclusive_group()
    voice.add_argument("--voice", dest="voice", action="store_true", default=True)
    voice.add_argument("--no-voice", dest="voice", action="store_false")
    parser.add_argument("--voice-background", action="store_true")
    parser.add_argument("--learning-dir", type=Path)
    parser.add_argument("--voice-listen-seconds", type=int, default=20)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--download-model", action="store_true")
    parser.add_argument("command", nargs="?", choices=("doctor",))
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "doctor":
        return doctor()
    if args.voice_listen_seconds < 5:
        parser.error("--voice-listen-seconds must be at least 5")
    try:
        config = load_config(args.config)
        configure_logging(config.app.log_level)
        if args.download_model:
            from pie.inputs.gesture.engine import ensure_model
            print(f"Hand model ready: {ensure_model(config.gesture.model_path or None, download=True)}")
            return 0
        if args.voice:
            print("Voice capture arrives in Phase 2A; phrase parsing is available now.")
        run(camera=args.camera if args.camera is not None else config.gesture.camera,
            no_actions=args.no_actions, game_profile=args.game_profile,
            steer_sensitivity=args.steer_sensitivity,
            arm_hold_seconds=config.gesture.arm_hold_seconds,
            model_path=config.gesture.model_path, preview=config.gesture.preview,
            learning_dir=args.learning_dir)
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
