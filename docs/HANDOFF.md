# Pie handoff log

## Phase 0S — foundation branch started
- Branch: phase-0s-foundation
- Package identity: pie-assistant, version 0.1.0, Python >=3.12,<3.13.
- Added project metadata, default TOML configuration, ignore rules and roadmap.
- Added pure hand-feature normalization/classification helpers, game profiles/controller, bounded voice phrase parser, JSON learning persistence, macOS subprocess adapter and read-only CLI doctor.
- No camera capture, MediaPipe inference engine, microphone pipeline, AI provider, tool registry, MCP or UI is implemented yet.
- Initial starter tests were previously run in the build environment (8 passed); target Mac/Python 3.12 validation remains outstanding.

## Phase 1 — core runtime implementation in progress
- Added core/events.py: bounded per-subscriber queues, wildcard subscriptions, thread-safe publish scheduling, sync/async handler dispatch, exception isolation and shutdown.
- Added core/state.py: StopFlag and lock-protected RuntimeState snapshots.
- Added core/config.py: frozen config dataclasses, defaults, strict TOML validation, typed environment overrides and path expansion.
- Added core/daemon.py: owned event-loop thread, ordered module startup, reverse shutdown and partial-start rollback.
- Added unit tests for event delivery/thread publishing/handler isolation, state, config and daemon order.
- Tests use stdlib asyncio and pytest; no pytest-asyncio dependency.
- Not yet verified on Python 3.12/macOS. GitHub CI has not yet passed. Phase 1 is NOT accepted.
- Known follow-up: complete strict configuration coverage for all documented environment keys, improve daemon signal/stop integration, and add concurrency/overflow/slow-subscriber tests.
