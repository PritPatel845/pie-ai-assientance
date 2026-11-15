from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from pie.paths import logs_dir


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    if root.handlers:
        return
    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    root.addHandler(console)
    try:
        directory = logs_dir(create=True)
        file_handler = RotatingFileHandler(directory / "pie.log", maxBytes=2_000_000,
                                           backupCount=5, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s: %(message)s"))
        root.addHandler(file_handler)
    except OSError:
        root.warning("File logging unavailable; continuing with console logging")
