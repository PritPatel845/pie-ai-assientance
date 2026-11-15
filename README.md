# Pie — Local-first macOS AI assistant

Pie is a phased, safety-first personal assistant for Apple Silicon macOS. It is designed to combine voice, gestures, deterministic commands, cloud AI and local AI while ensuring every real-world action passes through explicit permission and audit controls.

## Project status

**Phase 0S is in progress. This branch is not a complete assistant.** The current implementation includes the initial package foundation, gesture feature helpers, game profiles, a bounded voice phrase parser, local learning-data persistence, a macOS subprocess boundary, a read-only doctor command and initial tests.

Not yet implemented: live camera/MediaPipe engine, microphone capture and offline speech pipeline, daemon/event bus/config loader, AI provider routing, tool registry and permission UI, MCP, app integrations, game auto-detection, menu-bar UI and hardening/launch agent.

## Requirements

- macOS on Apple Silicon
- Python 3.12 (the project requires `>=3.12,<3.13`)
- Create an isolated environment: `python3.12 -m venv .venv`
- Install: `.venv/bin/python -m pip install -e '.[dev]'`
- Run tests: `.venv/bin/python -m pytest -q`
- Run diagnostics: `.venv/bin/python -m pie doctor`

Optional macOS dependencies are installed separately; the doctor command does not access the camera or microphone.

## Safety principles

- Never execute model-generated shell commands.
- Use argv lists, `shell=False`, timeouts and allow-listed executables.
- All future real-world actions must pass through the tool registry and permission gate.
- Destructive, external or irreversible actions require explicit confirmation.
- No credentials or secrets belong in source control or logs.
- Unit tests use fakes; camera, microphone, network, GUI and real apps are manual checks.

## Build order

See [docs/ROADMAP.md](docs/ROADMAP.md), [docs/CONTRACTS.md](docs/CONTRACTS.md) and [docs/HANDOFF.md](docs/HANDOFF.md). Phases are completed in order and are not tagged complete until their acceptance gates pass.
