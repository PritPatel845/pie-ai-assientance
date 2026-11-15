# Pie

Pie is a local-first macOS hand-gesture and voice-control foundation. Phase 0S contains
pure gesture classification, a deterministic frame processor, optional camera inference,
macOS action adapters, game profiles, a phrase parser, and local learning persistence.

## Requirements
- macOS on Apple Silicon
- Python 3.12
- Install package and development tools: `python -m pip install -e ".[dev,mac]"`

The camera runtime uses MediaPipe Tasks and the Hand Landmarker model. The model is not
silently downloaded: run `python -m pie --download-model` as an explicit network action.

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

See docs/CONTRACTS.md, docs/ARCHITECTURE.md, and scripts/manual_checks/phase0s.md.
