#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PYTHON="${PIE_PYTHON:-$ROOT/.venv/bin/python}"
cd "$ROOT"

echo '=== Pie Phase 0S macOS environment audit (read-only; no camera or microphone access) ==='
echo "Repository: $ROOT"
echo "Architecture: $(uname -m)"
sw_vers || true
echo "Homebrew: $(command -v brew || echo NOT_FOUND)"
echo "Python 3.12: $(command -v python3.12 || echo NOT_FOUND)"
if [[ ! -x "$PYTHON" ]]; then
  if command -v python3.12 >/dev/null 2>&1; then
    PYTHON="$(command -v python3.12)"
  else
    echo "Python 3.12 interpreter not found; expected $ROOT/.venv/bin/python or python3.12" >&2
    exit 2
  fi
fi
echo "Using Python: $PYTHON"

"$PYTHON" - <<'PY'
from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
import platform
import sys
from pathlib import Path

print(f'Python: {sys.version.split()[0]} ({sys.executable})')
print(f'Platform: {platform.platform()}')
for module, distribution in (
    ('cv2', 'opencv-python'),
    ('numpy', 'numpy'),
    ('mediapipe', 'mediapipe'),
    ('pyautogui', 'pyautogui'),
    ('Quartz', 'pyobjc-framework-Quartz'),
    ('AppKit', 'pyobjc-framework-Cocoa'),
):
    try:
        loaded = importlib.import_module(module)
        version = getattr(loaded, '__version__', None)
        if version is None:
            try:
                version = importlib.metadata.version(distribution)
            except importlib.metadata.PackageNotFoundError:
                version = 'installed (version unavailable)'
        print(f'{module}: OK ({version})')
    except Exception as exc:
        print(f'{module}: FAIL ({type(exc).__name__}: {exc})')

try:
    import mediapipe as mp

    vision = mp.tasks.vision
    checks = (
        ('HandLandmarker', hasattr(vision, 'HandLandmarker')),
        ('HandLandmarkerOptions', hasattr(vision, 'HandLandmarkerOptions')),
        ('RunningMode.VIDEO', hasattr(vision.RunningMode, 'VIDEO')),
        ('BaseOptions', hasattr(mp.tasks, 'BaseOptions')),
        ('Image', hasattr(mp, 'Image')),
        ('ImageFormat.SRGB', hasattr(mp.ImageFormat, 'SRGB')),
    )
    for name, ok in checks:
        print(f'MediaPipe API {name}: {"OK" if ok else "MISSING"}')
except Exception as exc:
    print(f'MediaPipe Tasks API: FAIL ({type(exc).__name__}: {exc})')

try:
    import pyautogui

    print(f"PyAutoGUI playpause key: {'AVAILABLE' if 'playpause' in pyautogui.KEYBOARD_KEYS else 'MISSING'}")
except Exception as exc:
    print(f'PyAutoGUI key table: FAIL ({type(exc).__name__}: {exc})')

model = Path('assets/hand_landmarker.task')
if model.is_file():
    digest = hashlib.sha256(model.read_bytes()).hexdigest()
    print(f'Model: FOUND ({model.stat().st_size} bytes; SHA-256 {digest})')
else:
    print('Model: NOT FOUND at assets/hand_landmarker.task')
PY

if [[ -x /usr/bin/mdfind ]]; then
  echo '=== Spotlight mdfind syntax smoke test ==='
  /usr/bin/mdfind -onlyin /Applications 'kMDItemKind == "Application" && kMDItemDisplayName == "*Safari*"' >/dev/null
  echo 'mdfind query syntax: accepted'
else
  echo 'mdfind: NOT FOUND'
fi

echo '=== Audit complete. No camera, microphone, cursor, or keyboard actions were performed. ==='
