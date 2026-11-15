# Pie

Pie is a local-first macOS hand-gesture and voice-control foundation. Phase 0S contains
pure gesture classification, a deterministic frame processor, optional camera inference,
macOS action adapters, game profiles, a phrase parser, and local learning persistence.

## Requirements
- macOS on Apple Silicon
- Python 3.12
- Install package and development tools: `python -m pip install -e ".[dev,mac]"`

**Packaging validation is still open:** MediaPipe 0.10.35 publishes a macOS arm64 wheel,
but its PyPI metadata also declares `opencv-contrib-python` while this project pins
`opencv-python`. Do not separately install or upgrade either OpenCV distribution until
the target-Mac install is checked; see `docs/HANDOFF.md`. The Linux CI job intentionally
does not claim to validate the macOS extra.

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
