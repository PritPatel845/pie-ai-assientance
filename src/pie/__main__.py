from __future__ import annotations

import argparse
import platform
import sys
from pathlib import Path

from pie.version import __version__


def _doctor() -> int:
    print(f"Pie {__version__}")
    print(f"Python: {sys.version.split()[0]}")
    print(f"Executable: {sys.executable}")
    print(f"Platform: {platform.platform()}")
    for module in ("cv2", "mediapipe", "pyautogui", "Quartz", "numpy"):
        try:
            imported = __import__(module)
            version = getattr(imported, "__version__", "installed")
            print(f"{module}: OK ({version})")
        except ImportError:
            print(f"{module}: NOT INSTALLED")
    home = Path.home() / ".pie"
    for name in ("config.toml", "state", "logs", "models", "learning"):
        path = home / name
        print(f"{path}: {'exists' if path.exists() else 'not created'}")
    model = Path(__file__).resolve().parents[3] / "assets" / "hand_landmarker.task"
    print(f"Hand model: {'found' if model.is_file() else 'not found'} ({model})")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="pie", description="Pie personal assistant")
    parser.add_argument("--version", action="version", version=f"Pie {__version__}")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("doctor", help="Read-only environment diagnostic")
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--no-actions", action="store_true")
    parser.add_argument("--game-profile", choices=("asphalt", "temple-run", "counter-strike"))
    parser.add_argument("--steer-sensitivity", type=float, default=0.004)
    parser.add_argument("--voice", dest="voice", action="store_true", default=True)
    parser.add_argument("--no-voice", dest="voice", action="store_false")
    parser.add_argument("--voice-background", action="store_true")
    parser.add_argument("--learning-dir")
    parser.add_argument("--voice-listen-seconds", type=int, default=20)
    args = parser.parse_args()
    if args.command == "doctor":
        return _doctor()
    if args.voice_listen_seconds < 5:
        parser.error("--voice-listen-seconds must be at least 5")
    print("Pie Phase 0S foundation: camera/audio runtime is not yet connected.")
    print("Use `pie doctor` to inspect optional dependencies. No actions were performed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
