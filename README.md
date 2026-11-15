# Pie

Pie is a local-first macOS hand-gesture and voice-control foundation. Phase 0S contains
pure gesture classification, a deterministic frame processor, optional camera inference,
macOS action adapters, game profiles, a phrase parser, and local learning persistence.

## Requirements
- macOS on Apple Silicon
- Python 3.12
- For pure-module development and tests: `python -m pip install -e ".[dev]"`

**Do not install the `[mac]` extra yet.** Packaging validation is blocked: MediaPipe
0.10.35 declares `opencv-contrib-python`, while Pie's frozen dependency pins
`opencv-python`. Both distributions provide the same `cv2` namespace, and OpenCV says
to install only one. Installing `.[mac]` would attempt to install both. The target-Mac
audit now reports the installed distributions and MediaPipe's declared requirement.
An approved dependency-contract resolution and a tested macOS installation are required
before camera runtime setup; see `docs/HANDOFF.md`. Linux CI does not validate the macOS extra.

The verified MediaPipe Hand Landmarker model is bundled at `assets/hand_landmarker.task`
for offline-first startup. Runtime path resolution checks the configured model path, the
bundled asset, then `~/.pie/models/`. If you intentionally need to fetch it again, run
`scripts/download_model.sh`; it checks the exact byte size and SHA-256 before accepting
either the official Google download or the mirror. `python -m pie --download-model` is
also available as an explicit network action into `~/.pie/models/`.

## Commands
```bash
python -m pie --version
python -m pie doctor
python -m pie --no-actions --no-voice
python -m pie --camera 1 --no-actions --no-voice
```

Hold an open palm continuously for two seconds to arm. Use `--no-actions` for safe
preview and classification without controlling other applications. Voice phrase parsing
is included; microphone capture arrives in Phase 2A.

## Safety and limitations
Camera and synthetic input permissions are granted by macOS to the executable running
Python. The preview and OpenCV GUI run on the main thread. No arbitrary shell command
is generated from speech or model output. Real-world actions are disabled with
`--no-actions`.

Before the manual camera check, run `scripts/manual_checks/audit_macos.command` for a read-only
architecture, dependency, MediaPipe API, PyAutoGUI key, model, and Spotlight audit. It does
not access the camera or microphone.

See docs/CONTRACTS.md, docs/ARCHITECTURE.md, and scripts/manual_checks/phase0s.md.
