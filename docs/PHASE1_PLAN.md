# Phase 1 implementation plan (Path B / Phase 0S)

Status: kickoff branch created; implementation has not started. The Phase 0S code and automated checks are green at commit 9089a89ec397aaaa66c533a361506c3799a1f2a5. The Phase 0S handoff records the target-Mac evidence and owner-reported manual checks.

## Gate

The source specification requires the pie-phase-0-done Git tag and a green pytest suite. The current Phase 0S push and PR workflows passed; the tag still needs to be created and verified before Phase 1 implementation begins.

## Goal

Add the asyncio EventBus, daemon lifecycle, full config loader, and gesture/voice event publication. This phase adds observability and plumbing only. Existing cursor, click, volume, media, game, and voice-command actions must continue through their existing execution paths; do not move actions onto events.

## Path B adaptation

The Phase 0S FrameProcessor.process loop body is already extracted. Publish events around it from the gesture runner. tests/test_gesture_events.py must drive the frame processor directly using fake landmarks and a fake frame source; no cv2 or hardware is needed.

## Files allowed

Create: src/pie/events.py; src/pie/core/daemon.py; src/pie/core/state.py; src/pie/inputs/text.py; config/pie.default.toml; tests/test_events.py; tests/test_config.py; tests/test_daemon.py; tests/test_gesture_events.py; scripts/manual_checks/phase1.md.

Modify: src/pie/config.py; src/pie/__main__.py; src/pie/logging_setup.py; src/pie/inputs/gesture/runner.py; src/pie/inputs/voice/pipeline.py; pyproject.toml; docs/ARCHITECTURE.md. Do not modify any other paths without explicit approval.

## Work sequence

1. Re-read docs/CONTRACTS.md and current config/runner/voice/CLI implementations in full.
2. Implement EventBus per contract: any-thread non-blocking publish, one bounded FIFO queue and dispatcher per subscriber, fnmatch topic matching, overflow policy and warning throttling, sync handlers in default executor, async handlers awaited, exception isolation, idempotent unsubscribe, wait_for timeout cleanup, and safe publish after loop shutdown.
3. Implement StopFlag and immutable thread-safe RuntimeState snapshots.
4. Implement Daemon: dedicated pie-loop thread, ordered module startup, reverse-order bounded stop, rollback on module startup failure, idempotent lifecycle, signal handling only on main thread, and camera/main function on caller thread.
5. Complete frozen config dataclasses and packaged config/pie.default.toml; preserve defaults < TOML < typed environment < CLI precedence, strict unknown-key/type errors, path expansion, and no directory creation during load.
6. Add gesture events: throttled input.gesture.state, rising-edge/debounced input.gesture.event, and system.mode changes. Reuse computed features and preserve existing actions.
7. Add voice wake/listening/transcript events after existing wake gating; do not alter parser or command execution.
8. Add pie run --print-events and pie config show while preserving existing CLI flags and no-bus behaviour.
9. Add hardware-free tests for event ordering, multi-thread delivery, slow subscribers, overflow, exception isolation, wait_for, no leaked threads, daemon rollback/shutdown, config precedence, and gesture edges/debounce.
10. Add architecture diagram, Phase 1 manual checklist, and handoff report.

## Acceptance

- Full Phase 0S test suite remains unchanged and green.
- pytest, Ruff lint/format, and mypy pass.
- No-bus behaviour is unchanged from Phase 0S.
- Idle CPU with no hand in view is measured and no higher than Phase 0S.
- Architecture documents threads, loop, bus, and modules.
- Handoff documents public symbols, emitted topics, and how to add a Module.
- Manual check verifies state events around 10 Hz, edge events, voice events, existing command execution, and Ctrl+C shutdown in under 3 seconds with camera release.

## Forbidden

No moving actions onto events, no tools/brain/UI, no new runtime dependencies, and no changes to topic names or payload keys in docs/CONTRACTS.md.