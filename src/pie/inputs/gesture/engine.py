from __future__ import annotations

import hashlib
import urllib.request
from pathlib import Path

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/1/hand_landmarker.task"
)
MODEL_MIRROR_URL = "https://huggingface.co/Leo-TX/mediapipe-hand/resolve/main/hand_landmarker.task"
MODEL_URLS = (MODEL_URL, MODEL_MIRROR_URL)
MODEL_BYTES = 7_819_105
MODEL_SHA256 = "fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1"


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
        if candidate.is_file() and candidate.stat().st_size == MODEL_BYTES:
            if sha256_file(candidate) == MODEL_SHA256:
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
            "Hand model not found or failed integrity validation. "
            "Run with explicit --download-model to fetch it."
        )
    target = Path.home() / ".pie" / "models" / "hand_landmarker.task"
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".task.tmp")
    errors: list[str] = []
    for url in MODEL_URLS:
        request = urllib.request.Request(url, headers={"User-Agent": "PieAssistant/0.1"})
        try:
            with (
                urllib.request.urlopen(request, timeout=timeout) as response,
                temporary.open("wb") as out,
            ):
                while chunk := response.read(1024 * 1024):
                    out.write(chunk)
            if temporary.stat().st_size != MODEL_BYTES:
                raise ValueError("unexpected byte size")
            if sha256_file(temporary) != MODEL_SHA256:
                raise ValueError("SHA-256 mismatch")
            temporary.replace(target)
            return target
        except Exception as exc:
            errors.append(f"{url}: {type(exc).__name__}: {exc}")
            temporary.unlink(missing_ok=True)
    details = " | ".join(errors)
    raise RuntimeError(f"Unable to download a verified Hand Landmarker model: {details}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
