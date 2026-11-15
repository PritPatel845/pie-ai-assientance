# Pie handoff log

## Phase 0S — clean-room implementation in progress
Branch: phase-0s-implementation. Target Python >=3.12,<3.13 on Apple Silicon macOS.

### Built so far
- Pure landmark geometry and hand predicates in inputs/gesture/features.py.
- Gesture profiles and key controller interface in inputs/gesture/game.py.
- Pure frame state machine and typed action objects in inputs/gesture/frame.py.
- Optional MediaPipe Tasks model resolution/download helper in inputs/gesture/engine.py.
- Camera runner, HUD, action sink and guaranteed cleanup in inputs/gesture/runner.py.
- Learning persistence with bounded samples, 250 ms sample throttling, 5 s flush cadence,
  atomic replacement, and redaction for typed dictation.
- Pure voice phrase parser and legacy rule executor seam; microphone capture is intentionally
  deferred to Phase 2A.
- macOS adapter with injectable subprocess runner and lazy Quartz/pyautogui imports.
- Config, paths, rotating logs, CLI doctor, and manual hardware checklist.
- Initial unit tests for frame processor, config, Mac adapter, learning and voice executor.

### Contract deltas for clean-room path
1. Omitted legacy/ and root jarvis.py.
2. Omitted ~/.jarvis_learning migration.
3. Renamed section 10 to FOUNDATION BEHAVIOUR (specified by Phase 0S).

### Current verification status — 2026-11-15

The target Apple Silicon Mac audit and interactive checks have now been run by the project owner.
The owner reports that the Phase 0S camera/gesture, cursor, media, screenshot, application
lookup, and safe-exit checks are working. Detailed evidence and remaining caveats are recorded
in the dated verification entry at the end of this file.

- The approved OpenCV dependency change is implemented: the macOS extra uses only
  `opencv-contrib-python==4.11.0.86`; the target virtual environment reports that package
  installed and `opencv-python` absent.
- Target Mac: arm64, macOS 27.2.1, Python 3.12.14. The read-only audit passed the required
  MediaPipe Tasks API, PyAutoGUI key, Quartz/AppKit, model hash, and Spotlight checks.
- Latest target-Mac test run: **207 passed**. `pie doctor` reports all runtime dependencies
  and the bundled model present.
- Latest GitHub Actions test job for branch head
  `1adb89859fd04ee2b4eea53f6362cd93d15583d8` passed. The push and pull-request workflows
  both completed successfully for that exact SHA.
- Phase 0S is not yet formally accepted. Keep PR #2 open and draft; do not merge, tag
  `pie-phase-0-done`, or begin Phase 1 until the acceptance checklist and evidence are
  reconciled and reviewed.

### Public symbols
- features: Landmark, distance, hand_size, finger_extended, is_pinch, is_open_palm,
  is_thumb_extended, is_four_finger, is_fist, is_two_finger, is_three_finger,
  is_thumb_up, is_thumb_down, classify_desktop, normalize_hand.
- game: GAME_PROFILES, PROFILE_KEYS, MAC_KEY_CODES, game_gesture, GameController.
- frame: FrameProcessor, FrameResult, MoveCursor, DoubleClick, Mute, PlayMedia,
  StopMedia, RunVoiceCommand, Scroll, SetVolume, KeyAction, Tap, MouseClick.
- engine: resolve_model_path, ensure_model, sha256_file.
- runner: ActionSink, draw_hand, draw_hud, run.
- learning: LearningEngine.
- voice: VOICE_WAKE_WORDS, extract_wake_command, parse_voice_command,
  LegacyRuleExecutor, VoiceController.
- platform.mac: MacController, SYSTEM_APP_ALIASES, resolve_system_application.
- config: Config, AppConfig, GestureConfig, VoiceConfig, UiConfig, load_config.
- paths: pie_home, config_path, state_dir, logs_dir, models_dir, learning_dir.

### Next
1. Obtain an approved resolution for the frozen MediaPipe/OpenCV dependency conflict. A
   contract change may be required; do not install both OpenCV distributions or silently
   alter the frozen package pin.
2. Run `scripts/manual_checks/audit_macos.command` on the target Mac.
3. Run `scripts/manual_checks/phase0s.md` for camera, HUD, permissions, cursor, and cleanup.
4. Verify `playpause` and Spotify/Music control on the target Mac.
5. Only after every gate passes, tag Phase 0S and start Phase 1 from that tag.


## Phase 0S acceptance ledger — 2026-11-15

### Automated verification

- Latest GitHub Actions runs for code commit `f906bc23546831d9446d60f864fb8689183cd7b2`: push https://github.com/PritPatel845/pie-ai-assientance/actions/runs/43673643751 and pull request https://github.com/PritPatel845/pie-ai-assientance/actions/runs/43673646615 (both passed). The README now directs contributors to install only the `[dev]` extra until the macOS dependency contract is resolved.
- Earlier Linux/Python 3.12 baseline: `pytest -q` **206 passed**. The latest target-Mac run is 207 passed; see the dated verification entry below.
- `ruff check .`: passed.
- `ruff format --check .`: passed.
- `mypy src/pie`: passed; no issues in 20 source files.
- `python -m pie doctor`: exited successfully on the CI runner.
- CI is Linux/Python 3.12. It is not evidence of macOS/Apple Silicon or camera/permission compatibility.
- `scripts/start_pie.command`, `scripts/download_model.sh`, and `scripts/manual_checks/audit_macos.command` are executable (`100755`). CI syntax-checks both maintenance scripts and verifies their executable bits.
- The model-asset job downloaded the official Google model, verified its exact 7,819,105-byte size and SHA-256, then committed it as `9e173f61fc8cae8883932c879a5623666f38ae51`. A regression test now re-verifies the bundled binary on every test run.

### Configuration reference

| Section | Keys | Defaults |
|---|---|---|
| `[app]` | `name`, `log_level` | `pie`, `INFO` |
| `[gesture]` | `camera`, `preview`, `arm_hold_seconds`, `steer_sensitivity`, `state_hz`, `model_path` | `0`, `true`, `2.0`, `0.004`, `10`, `""` |
| `[voice]` | `enabled`, `wake_words`, `listen_seconds`, `language` | `true`, `["hey pie","pie","pi","jr","j r","jay r","jarvis"]`, `20`, `"en"` |
| `[ui]` | `host`, `port` | `127.0.0.1`, `8765` |

Precedence is: repository default TOML < `~/.pie/config.toml` < typed `PIE_<SECTION>_<KEY>` environment variables < `cli_overrides`. Unknown TOML keys and unknown environment names for a known section raise `ConfigError`. Boolean environment values accept `true/false/1/0/yes/no`; list values accept JSON arrays. `gesture.model_path` expands `~`. Loading configuration does not create directories.

### Gesture precedence and profiles

Desktop classification is first-match in this exact order:

1. `THUMB UP / PLAY`
2. `THUMB DOWN / STOP`
3. `PINCH / OPEN`
4. `THREE FINGER / OPEN`
5. `OPEN PALM`
6. `FIST / VOICE`
7. `TWO-FINGER SWIPE`
8. `INDEX / POINTER`

Game gesture recognition checks pinch, thumb-up, two-finger, fist, three-finger, four-finger, then open-palm swipe/palm-up/palm-down; otherwise `GAME READY`.

Built-in profiles:
- `asphalt`: `racing`; left/right arrows, accelerate up, brake down, nitro space.
- `temple-run`: `runner`; left/right arrows, jump up, slide down.
- `counter-strike`: `fps`; A/D/W/S and space.

To add a profile in this foundation, add a unique entry to `GAME_PROFILES` in `src/pie/inputs/gesture/game.py` with one supported style (`racing`, `runner`, `fps`) and its action-to-key mapping. Ensure every mapped key exists in `MAC_KEY_CODES`; add it to the profile selector/CLI only if it is intended to be selectable, then add profile and `FrameProcessor` regression tests. The current phase does not yet support user-editable profile files.

### Voice parser precedence

The parser checks exact phrases first, then volume patterns, search patterns, then `open/launch/start`, then `type/write/enter`. Matching is lower-cased and whitespace-collapsed. Hostile command-looking text remains plain argument data; it is not executed as shell input. Wake-word matching is anchored at the beginning and requires a word/punctuation boundary; `pizza` and `pied` do not match.

### Regression fixes recorded

- Desktop hand normalization now rotates the wrist-to-middle-MCP vector toward image-up.
- Added and tested the specified `MacController.show_voice_activation()` notification (`PIE ACTIVE`, configured duration).
- Media commands now target an already-running Spotify or Music process through AppleScript, then fall back to the system `playpause` key through PyAutoGUI; deterministic tests cover app selection and fallback. Actual target-Mac key availability remains a manual audit item.
- Counter-Strike `KeyAction` names resolve through the selected profile to A/D/W/S keycodes.
- Temple Run handles swipe left/right and palm up/down actions.
- Runner/fist/pinch and game-key state reset on hand loss/mode changes; held keys are released.
- Clean-room Path B no longer copies `~/.jarvis_learning`.
- Config environment parsing, strict unknown-key checks, and CLI-over-config precedence are covered by regression tests.
- Ruff CI is read-only; it never formats and pushes commits from a pull-request merge checkout.
- `FrameProcessor` action-list annotations satisfy strict mypy.
- The voice parser now has a 90-row phrase matrix plus punctuation-boundary wake-word tests.
- Runner cleanup now covers failures during model setup and controller initialization, not only exceptions in the capture loop.
- Mode changes clear stale desktop scroll and volume state; malformed learning JSON structures are quarantined rather than crashing startup.
- Doctor reports native-library import errors without crashing and does not create `~/.pie` directories.
- Tests now identify the exact Phase 0S PDF section/page for their covered module.
- Model path resolution and explicit downloads verify the pinned byte size and SHA-256; invalid or partial downloads are removed. Downloads try Google's official URL first, then a Hugging Face mirror of the same model; the identical SHA-256 is required for either source.
- `scripts/manual_checks/audit_macos.command` performs a read-only architecture/dependency/Tasks API/PyAutoGUI-key/model/Spotlight audit without accessing camera or microphone.
- Learning ring-buffer test isolates the bounded-buffer assertion from periodic disk-flush I/O.

### Exact verification commands

```bash
.venv/bin/python -m pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy src/pie
.venv/bin/python -m pie doctor
.venv/bin/python -m pie --no-actions --no-voice
```

### Historical blockers (superseded by target-Mac verification below)

- `assets/hand_landmarker.task` is committed (7,819,105 bytes). The model-asset workflow downloaded it from Google's official URL and verified SHA-256 `fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1` before committing. `ensure_model()` independently verifies both size and hash at runtime.
- The actual target Mac has not been audited here: `uname -m`, `sw_vers`, Homebrew Python 3.12 path, and imports/versions for MediaPipe 0.10.35 Tasks API, OpenCV, PyAutoGUI, Quartz, and AppKit remain unverified.
- Packaging risk to resolve on the target Mac: PyPI's MediaPipe 0.10.35 metadata advertises a macOS 11+ arm64 wheel, but its dependencies include `opencv-contrib-python`, `sounddevice`, and `matplotlib`; the Phase 0S dependency contract names `opencv-python`. Do not blindly install both OpenCV wheel distributions; determine a compliant, working install strategy on the target Mac and record it before accepting the phase.
- `scripts/manual_checks/audit_macos.command` and `scripts/manual_checks/phase0s.md` have not been run on the target Mac. Camera preview, HUD poses, camera release, Accessibility permission, and safe cursor/pinch behaviour remain unverified.
- macOS-specific media-key behaviour and app automation have not been verified on the target Mac. `play_media()`/`stop_media()` now target an already-running Spotify or Music process via AppleScript and fall back to PyAutoGUI's `playpause` key; CI tests both routing and fallback. The actual key's availability and behaviour still require target-Mac verification.
- Phase 0S is **not accepted**. Do not create `pie-phase-0-done` or begin Phase 1 until the model and Mac/manual acceptance gates are satisfied.


## Phase 0S dependency contract change — 2026-11-15

The project owner explicitly approved a narrowly scoped change: replace
`opencv-python==4.11.0.86` with `opencv-contrib-python==4.11.0.86` in the `[mac]`
optional extra. All other dependency pins, including `mediapipe==0.10.35`, remain
unchanged. The approval, rationale, explicit non-changes, and acceptance tests are recorded
in `docs/CONTRACT_CHANGE_REQUEST.md`.

Implemented on `phase-0s-implementation`:
- `pyproject.toml` now selects only `opencv-contrib-python==4.11.0.86` for the macOS extra.
- README and the Phase 0S manual checklist describe the approved dependency and install path.
- The read-only macOS audit checks the exact contrib pin and flags an accidental additional
  `opencv-python` distribution.
- No Phase 0S contract sections 3–8, runtime code, or other dependency pins were changed.

External wheel metadata review:
- MediaPipe 0.10.35 has a macOS 11+ ARM64 wheel.
- OpenCV contrib 4.11.0.86 has a macOS 13+ ARM64 abi3 wheel; the target reports macOS
  27.2.1 and CPython 3.12.14, so the published wheel tags are compatible.
- This metadata review does not establish successful installation or runtime operation.

### Target Mac verification — completed 2026-11-15

The target Mac audit, runtime dependency checks, and owner-reported manual checks are now
recorded in the dated verification entry below. This section supersedes the earlier
"verification still required" note. Formal Phase 0S acceptance remains pending until the
checklist wording and evidence are reviewed together.


## Target Mac verification update — 2026-11-15

### Environment and dependencies

- Repository branch: `phase-0s-implementation`.
- Verified branch head during this review: `1adb89859fd04ee2b4eea53f6362cd93d15583d8`.
- Hardware/platform: Apple Silicon arm64; macOS 27.2.1.
- Python: 3.12.14 from the project's `.venv-mac`.
- `opencv-contrib-python==4.11.0.86`: installed.
- `opencv-python`: not installed. The duplicate `cv2` distribution conflict is resolved.
- Runtime versions reported by `pie doctor`: OpenCV 4.11.0, NumPy 2.2.6,
  MediaPipe 0.10.35, PyAutoGUI 0.9.54; Quartz and AppKit installed.
- Bundled `assets/hand_landmarker.task` found; expected 7,819,105-byte model and
  SHA-256 `fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1`
  were confirmed by the read-only audit.
- The audit also confirmed MediaPipe Tasks symbols, VIDEO mode, BaseOptions, Image,
  SRGB format, PyAutoGUI `playpause`, and Spotlight query syntax. The audit is read-only
  and does not access camera or microphone.

### Target-Mac automated checks

- `pytest -q`: **207 passed** (latest user-reported run, 0.11 seconds).
- `pie doctor`: completed and reported the expected platform, dependencies, model,
  and ~/.pie directory state.
- Screenshot regression test: `tests/test_mac_adapter.py` **7 passed**.
- Screenshot adapter: `MacController().screenshot()` returned `True`; a
  `Pie Screenshot` PNG was observed on the Desktop.
- Preview application lookup returned `True`.
- Cursor-control application was reported working by the owner.
- The earlier complete Mac quality run reported Ruff lint passed, 34 files formatted,
  and strict mypy with no issues in 20 source files. These quality checks predate the
  final OpenCV environment cleanup; they were not re-run in the latest 207-test command.

### Interactive checks — owner confirmation

The project owner confirmed that the manual functionality previously listed as remaining
is working, including camera preview/gesture poses, cursor interaction, media controls,
screenshot creation, application lookup, and safe exit/cleanup. Earlier direct checks also
confirmed the camera preview closes with q, Preview lookup succeeds, and the media adapter
returns success for play and pause. Treat this as owner-reported manual verification, not
as automated CI coverage.

### GitHub CI and pull request

For branch head `1adb89859fd04ee2b4eea53f6362cd93d15583d8`:
- Push workflow run [43677472921](https://github.com/PritPatel845/pie-ai-assientance/actions/runs/43677472921):
  completed successfully; test job passed and model-asset job passed.
- Pull-request workflow run [43677475038](https://github.com/PritPatel845/pie-ai-assientance/actions/runs/43677475038):
  completed successfully; test job passed. The model-asset job was skipped in this PR run.
- PR [#2](https://github.com/PritPatel845/pie-ai-assientance/pull/2) remains open and draft;
  it is not merged.

### Voice scope and acceptance decision

Voice phrase parsing exists in Phase 0S, but microphone/voice capture is explicitly deferred
to Phase 2A. Therefore the manual checklist must not require voice-captured play/pause
commands in Phase 0S. Media routing/fallback should be checked through the available
Phase 0S action/gesture path and direct app/system behavior.

The current evidence is strong and the owner reports the interactive checks working, but
this log does not itself declare Phase 0S accepted. Review the complete Phase 0S PDF
acceptance requirements against the implementation and this evidence before closing the
gate. Do not merge PR #2, create `pie-phase-0-done`, or start Phase 1 until that review
explicitly confirms every acceptance criterion.

## Phase 0S final verification — 2026-11-15

- Final implementation commit: 9089a89ec397aaaa66c533a361506c3799a1f2a5.
- The synthetic test hand now supplies a distinct thumb-base landmark; this fixes the false four-finger classification in the regression fixtures. The FPS regression now asserts the forward-key press on the arming frame, where the state machine emits it.
- GitHub Actions push run https://github.com/PritPatel845/pie-ai-assientance/actions/runs/43678871735 and PR run https://github.com/PritPatel845/pie-ai-assientance/actions/runs/43678875609 both completed successfully for this exact commit.
- CI: ruff check ., ruff format --check ., pytest -q (212 passed), mypy src/pie, model downloader verification, and python -m pie doctor all passed. The push workflow's model-asset job also passed.
- Target Mac evidence remains as recorded above: arm64/macOS 27.2.1/Python 3.12.14, OpenCV contrib 4.11.0.86 only, MediaPipe Tasks API and model hash verified, pie doctor passed, and 207 tests passed in the earlier local run before the five new regression tests. The latest 212-test result is CI evidence, not a new local Mac test run.
- Owner-reported manual checks: camera preview and gesture poses work; q closes preview; cursor control works perfectly; screenshot creation and Preview lookup work; media adapter play/stop calls return success; safe exit/cleanup was reported working. These are manual reports, not CI tests.
- PR #2's push and pull-request checks are green at this commit. PR #2 remains open pending release finalization.
- The Phase 0S implementation and automated acceptance checks are complete. Do not claim a Git tag exists unless independently verified. The Phase 1 specification requires the pie-phase-0-done tag and a green test suite as its gate.

## Phase 1 kickoff plan — 2026-11-15 (Path B / Phase 0S)

Phase 1 scope is daemon, asyncio event bus, full config, and event publication only. The Phase 0S FrameProcessor.process loop body is already extracted; publish events around it from the runner and test event derivation directly through fakes. Preserve all existing action execution paths; do not move actions onto events.

### Allowed files

Create: src/pie/events.py, src/pie/core/daemon.py, src/pie/core/state.py, src/pie/inputs/text.py, config/pie.default.toml, tests/test_events.py, tests/test_config.py, tests/test_daemon.py, tests/test_gesture_events.py, and scripts/manual_checks/phase1.md.

Modify only: src/pie/config.py, src/pie/__main__.py, src/pie/logging_setup.py, src/pie/inputs/gesture/runner.py, src/pie/inputs/voice/pipeline.py, pyproject.toml, and docs/ARCHITECTURE.md. No other files without an approved scope change.

### Implementation sequence

1. Read and preserve docs/CONTRACTS.md; implement the thread-safe, non-blocking asyncio EventBus with per-subscriber FIFO queues, overflow handling, pattern subscriptions, exception isolation, and wait_for cleanup.
2. Add StopFlag and immutable thread-safe RuntimeState snapshots.
3. Add the daemon-owned event loop thread, ordered module startup, reverse bounded shutdown, rollback on startup failure, and main-thread camera execution.
4. Complete frozen config dataclasses, packaged default TOML, typed environment parsing, strict unknown-key errors, and pie config show.
5. Publish throttled gesture state, rising-edge gesture events, and mode changes from the runner without changing action decisions or moving actions onto the bus.
6. Publish voice wake/listening/transcript events after existing wake gating; preserve existing command execution.
7. Add pie run --print-events; preserve existing CLI flags and no-bus behaviour.
8. Add hardware-free concurrency, lifecycle, config, and gesture-event tests; write the Phase 1 manual check and architecture diagram.

### Phase 1 acceptance gates

- All Phase 0S tests remain unchanged and pass; new pytest, Ruff, and mypy checks pass.
- No-bus behaviour remains identical to Phase 0S.
- Idle CPU with no hand in view is measured and is not higher than Phase 0S.
- docs/ARCHITECTURE.md documents threads, loop, bus, and modules.
- Handoff records public symbols, emitted topics, and how to add a Module.
- Manual check: pie run --print-events; verify gesture state near 10 Hz, edge events, voice events and existing command execution; Ctrl+C exits in under 3 seconds and releases camera.

Forbidden in Phase 1: moving actions onto events, tools/brains/UI, new runtime dependencies, or changing topic names/payload keys in docs/CONTRACTS.md.


## Phase 1 implementation progress — 2026-11-15

### Release gate and repository state
- The release `pie-phase-0-done` is published and independently verified. The tag resolves to
  `fa2f0c6abee719d5c5def81cd7a91723c237816a`.
- PR #2 was merged into `main` at `4f1ff0f28af4f184d621ff735037a0bfa4858fc2`.
- Phase 1 work is isolated on branch `phase-1-implementation`; PR #3 targets `main`.

### Implemented so far
- Added `Event` and `EventBus` with thread-safe non-blocking publication, per-subscriber bounded
  queues, wildcard matching, executor/async handlers, overflow accounting/warnings,
  exception isolation, unsubscribe, and `wait_for`.
- Added `StopFlag`, immutable `RuntimeState` snapshots, and the daemon-owned `pie-loop`
  lifecycle with module registration, rollback, and bounded reverse-order shutdown.
- Added the default TOML config, frozen config loader integration, typed environment values,
  CLI overrides, and packaging data-file configuration.
- Added `TextInput`, optional voice event publication methods, and gesture state/mode/edge
  publication while retaining the original ActionSink execution path.
- Added `pie config show`, `pie run --print-events`, a Phase 1 architecture overview,
  a macOS manual checklist, and hardware-free tests for bus, lifecycle, and gesture edges.

### Current public additions
- `pie.events.Event`, `pie.events.EventBus`
- `pie.core.state.StopFlag`, `RuntimeState`, `StateSnapshot`
- `pie.core.daemon.Module`, `Daemon`
- `pie.inputs.text.TextInput`
- `pie.inputs.gesture.runner.GestureEventTracker`
- `pie.inputs.voice.pipeline.VoiceController` event methods:
  `publish_wake`, `publish_listening`, `publish_transcript`

### Config and topics
- Defaults remain `[app]`, `[gesture]`, `[voice]`, and `[ui]`; precedence is defaults,
  user TOML, typed `PIE_*` environment variables, then CLI overrides.
- Phase 1 publishes `system.started`, `system.stopping`, `system.warning`,
  `system.error`, `system.mode`, `input.gesture.state`, `input.gesture.event`,
  `input.voice.wake`, `input.voice.listening`, `input.voice.transcript`, and
  `input.text.command`. Payload schemas remain as specified in `docs/CONTRACTS.md`.

### Limitations and verification status
- Voice microphone capture and wake-word gating are still deferred to Phase 2A, as in the
  Phase 0S implementation. Phase 1 provides the event publication seam; it does not fake
  voice activity.
- Camera/GUI and all existing system actions remain on the caller/main thread. Event handlers
  must not execute actions.
- CI is still being stabilized for this implementation. Do not treat Phase 1 as accepted
  until the latest branch-head pytest, Ruff lint/format, mypy, model verification, and doctor
  jobs all pass.
- Exact verification commands: `pytest -q`, `ruff check .`,
  `ruff format --check .`, `mypy src/pie`, `python -m pie doctor`,
  `python -m pie config show`, and `python -m pie run --print-events`.
- Next: resolve any CI failures, add any missing acceptance tests, run the manual macOS
  checklist, measure idle CPU, and append the final Phase 1 handoff before merging PR #3.
