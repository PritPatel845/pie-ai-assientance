from __future__ import annotations

import argparse
import platform
import sys
from dataclasses import asdict
from pathlib import Path

from pie.core.config import load_config
from pie.core.daemon import Daemon
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


def _config_show(config_path: Path | None) -> int:
    config = load_config(config_path)
    for section, values in asdict(config).items():
        print(f"[{section}]")
        for key, value in values.items():
            print(f"{key} = {value!r}")
    return 0


def _run() -> int:
    daemon = Daemon()
    daemon.start()
    daemon.install_signal_handlers()
    print("Pie daemon running. Press Ctrl+C to stop.")
    daemon.wait()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="pie", description="Pie personal assistant")
    parser.add_argument("--version", action="version", version=f"Pie {__version__}")
    parser.add_argument("--config", type=Path, help="Optional TOML configuration file")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("doctor", help="Read-only environment diagnostic")
    subparsers.add_parser("run", help="Start the Pie daemon")
    config_parser = subparsers.add_parser("config", help="Configuration commands")
    config_sub = config_parser.add_subparsers(dest="config_command", required=True)
    config_sub.add_parser("show", help="Print the resolved configuration")
    args = parser.parse_args()
    if args.command == "doctor":
        return _doctor()
    if args.command == "config" and args.config_command == "show":
        try:
            return _config_show(args.config)
        except (OSError, ValueError) as exc:
            parser.error(str(exc))
    if args.command == "run":
        return _run()
    if args.command is None:
        print("Pie Phase 1 core runtime is available. Use pie run, pie config show, or pie doctor.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
