# Pie handoff log

## Phase 0S — foundation branch started

- Branch: `phase-0s-foundation`
- Package identity: `pie-assistant`, version `0.1.0`, Python `>=3.12,<3.13`
- Added project metadata, default TOML configuration, ignore rules and roadmap.
- Added pure hand-feature normalization/classification helpers, game profiles/controller, bounded voice phrase parser, JSON learning persistence, macOS subprocess adapter and read-only CLI doctor.
- No camera capture, MediaPipe inference engine, microphone pipeline, daemon, event bus, AI provider, tool registry, MCP or UI is implemented yet.
- Automated tests are being added; target Mac/Python 3.12 validation remains outstanding.
- Security note: no model-generated shell execution; OS subprocess adapter uses a fixed executable allow-list and shell=False.
- Next: finish Phase 0S engine/runner and acceptance suite; then Phase 1 only after the Phase 0S gate passes.
