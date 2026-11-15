from __future__ import annotations

import hashlib
import urllib.request
from pathlib import Path

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/1/hand_landmarker.task"
)
MIN_MODEL_BYTES = 1_000_000


def resolve_model_path(
    configured: str | Path | None = None, package_root: Path | None = None
) -> Path | None:
    candidates: list[Path] = []
    if configured:
        candidates.append(Path(configured).expanduser())
    root = package_root or Path(__file__).resolve().parents[4]
    candidates.extend(
        (
            root / "assets" / "hand_landmarker.task",
            Path.home() / ".pie" / "models" / "hand_landmarker.task",
        )
    )
    for candidate in candidates:
        if candidate.is_file() and candidate.stat().st_size > MIN_MODEL_BYTES:
            return candidate
    return None


def ensure_model(
    configured: str | Path | None = None,
    *,
    download: bool = False,
    package_root: Path | None = None,
    timeout: float = 30.0,
) -> Path:
    found = resolve_model_path(configured, package_root)
    if found is not None:
        return found
    if not download:
        raise FileNotFoundError(
            "Hand model not found. Run with explicit --download-model to fetch it."
        )
    target = Path.home() / ".pie" / "models" / "hand_landmarker.task"
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".task.tmp")
    request = urllib.request.Request(MODEL_URL, headers={"User-Agent": "PieAssistant/0.1"})
    with urllib.request.urlopen(request, timeout=timeout) as response, temporary.open("wb") as out:
        while chunk := response.read(1024 * 1024):
            out.write(chunk)
    if temporary.stat().st_size <= MIN_MODEL_BYTES:
        temporary.unlink(missing_ok=True)
        raise ValueError("Downloaded hand model is unexpectedly small")
    temporary.replace(target)
    return target


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
