#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import cv2
import mediapipe as mp

from pie.inputs.gesture.engine import ensure_model

POSES = ("palm", "fist", "pinch", "thumb_up", "thumb_down",
         "two_finger", "three_finger", "four_finger", "pointer")


def main() -> int:
    parser = argparse.ArgumentParser(description="Record one second of real hand landmarks per pose")
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--seconds", type=float, default=1.0)
    parser.add_argument("--output", type=Path, default=Path("tests/fixtures/real_poses"))
    args = parser.parse_args()
    if args.seconds <= 0:
        parser.error("--seconds must be positive")
    model = ensure_model()
    args.output.mkdir(parents=True, exist_ok=True)
    capture = cv2.VideoCapture(args.camera)
    if not capture.isOpened():
        capture.release()
        raise RuntimeError(f"Could not open camera {args.camera}")
    options = mp.tasks.vision.HandLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(model)),
        running_mode=mp.tasks.vision.RunningMode.VIDEO, num_hands=1,
    )
    try:
        with mp.tasks.vision.HandLandmarker.create_from_options(options) as landmarker:
            for pose in POSES:
                input(f"Show {pose.replace('_', ' ')} pose, then press Enter...")
                deadline = time.monotonic() + args.seconds
                samples = []
                while time.monotonic() < deadline:
                    ok, frame = capture.read()
                    if not ok:
                        continue
                    rgb = cv2.cvtColor(cv2.flip(frame, 1), cv2.COLOR_BGR2RGB)
                    result = landmarker.detect_for_video(
                        mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb),
                        int(time.monotonic() * 1000),
                    )
                    if result.hand_landmarks:
                        samples.append([[point.x, point.y, point.z]
                                        for point in result.hand_landmarks[0]])
                if not samples:
                    print(f"No hand landmarks captured for {pose}; skipping.")
                    continue
                destination = args.output / f"{pose}.json"
                destination.write_text(json.dumps({"pose": pose, "samples": samples},
                                                   indent=2), encoding="utf-8")
                print(f"Saved {len(samples)} samples: {destination}")
    finally:
        capture.release()
        cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
