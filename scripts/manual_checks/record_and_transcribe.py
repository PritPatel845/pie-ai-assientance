from __future__ import annotations

import argparse
import importlib
import time

import numpy as np

from pie.config import load_config
from pie.inputs.voice.stt import create_transcriber


def main() -> int:
    parser = argparse.ArgumentParser(description="Record a short sample and transcribe locally")
    parser.add_argument("--seconds", type=float, default=5.0)
    args = parser.parse_args()
    if not 1.0 <= args.seconds <= 15.0:
        parser.error("--seconds must be between 1 and 15")

    config = load_config().voice
    if config.stt_backend == "google" and not config.allow_cloud_stt:
        parser.error("Google STT requires voice.allow_cloud_stt=true")
    sounddevice = importlib.import_module("sounddevice")
    wanted = config.input_device.strip().lower()
    device: int | str | None = None
    if wanted:
        for index, info in enumerate(sounddevice.query_devices()):
            if wanted in str(info.get("name", "")).lower() and int(
                info.get("max_input_channels", 0)
            ) > 0:
                device = index
                break
        if device is None:
            parser.error(f"No microphone matches voice.input_device={config.input_device!r}")

    blocks: list[np.ndarray] = []

    def capture(indata: np.ndarray, frames: int, timing: object, status: object) -> None:
        del frames, timing, status
        blocks.append(np.asarray(indata[:, 0], dtype=np.float32).copy())

    print(f"Recording {args.seconds:.1f}s from {device or 'system default'}; speak now.")
    with sounddevice.InputStream(
        samplerate=16_000,
        channels=1,
        dtype="float32",
        blocksize=512,
        device=device,
        callback=capture,
    ):
        deadline = time.monotonic() + args.seconds
        while time.monotonic() < deadline:
            time.sleep(0.05)

    if not blocks:
        parser.error("No microphone samples were captured")
    audio = np.concatenate(blocks).astype(np.float32, copy=False)
    transcriber = create_transcriber(
        config.stt_backend, config.stt_model, allow_cloud=config.allow_cloud_stt
    )
    try:
        print(f"Backend: {transcriber.name}; transcribing locally...")
        print(f"Transcript: {transcriber.transcribe(audio, config.language)}")
    finally:
        transcriber.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
