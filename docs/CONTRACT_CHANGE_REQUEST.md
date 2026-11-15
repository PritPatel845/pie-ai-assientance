# Contract change request — Phase 0S OpenCV distribution

- **Status:** Approved by project owner; implementation in progress.
- **Approval:** Explicit approval received in ChatGPT on 2026-11-15.
- **Scope:** One dependency distribution-name change only.

## Requested change

In `pyproject.toml` under `[project.optional-dependencies].mac`, replace:

```toml
opencv-python==4.11.0.86
```

with:

```toml
opencv-contrib-python==4.11.0.86
```

Keep the OpenCV version exactly `4.11.0.86`. Keep `mediapipe==0.10.35`, NumPy, PyAutoGUI, both PyObjC pins, all other dependency pins, and all runtime/API contracts unchanged.

## Reason

The published MediaPipe 0.10.35 package metadata declares `opencv-contrib-python`.
OpenCV's package guidance explicitly says to install only one OpenCV wheel distribution
because the distributions share the `cv2` namespace. The previous combination would
request both `opencv-python` and `opencv-contrib-python` in the same environment.

The contrib 4.11.0.86 release publishes a macOS 13+ ARM64 abi3 wheel, compatible by wheel
tag with the project's CPython 3.12 target and the target Mac's reported macOS 27.2.1.
MediaPipe 0.10.35 publishes a macOS 11+ ARM64 wheel. Wheel availability is not proof of
successful installation or runtime behaviour; target-Mac verification remains required.

## Acceptance tests for this change

1. Resolve/install `.[mac,dev]` in a fresh target-Mac Python 3.12 virtual environment.
2. `python -m pip check` reports no broken requirements.
3. `opencv-contrib-python==4.11.0.86` is installed and `opencv-python` is absent.
4. `cv2`, MediaPipe Tasks, PyAutoGUI, Quartz, and AppKit import successfully.
5. The Phase 0S read-only audit reports the expected OpenCV distribution and version.
6. Complete the camera, gesture, permissions, cursor, cleanup, and media manual checks.

## Explicit non-changes

- No MediaPipe version change.
- No OpenCV version change.
- No second OpenCV distribution.
- No change to sections 3–8 of the frozen event, threading, config, permission, tool, or
  brain contracts.
- No Phase 1 work or Phase 0S acceptance implied by this approval.

## Evidence

- PyPI MediaPipe 0.10.35: https://pypi.org/project/mediapipe/0.10.35/
- PyPI opencv-contrib-python 4.11.0.86: https://pypi.org/project/opencv-contrib-python/4.11.0.86/
- OpenCV package installation guidance: https://pypi.org/project/opencv-contrib-python/
