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

### Not complete / not verified
- The target Mac audit has not been run: Apple Silicon architecture, macOS version, Homebrew
  Python 3.12, MediaPipe Tasks imports, Quartz/AppKit, and PyAutoGUI key support remain
  unverified on the actual device.
- The offline-first model is now committed at `assets/hand_landmarker.task` and CI verifies
  its exact size and SHA-256 on every test run. See the acceptance ledger below.
- Linux/Python 3.12 CI is green (205 tests, Ruff, strict mypy, and doctor); this does not
  establish macOS or camera compatibility.
- Real camera preview, HUD poses, camera release, Accessibility permission, and safe cursor
  control still require manual checks on the target Mac.
- Phase 0S is NOT accepted; do not tag pie-phase-0-done.

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
1. Resolve the MediaPipe/OpenCV packaging conflict on the target Mac and record the tested
   install procedure.
2. Run `scripts/manual_checks/audit_macos.command` on the target Mac.
3. Run `scripts/manual_checks/phase0s.md` for camera, HUD, permissions, cursor, and cleanup.
4. Verify `playpause` and Spotify/Music control on the target Mac.
5. Only after every gate passes, tag Phase 0S and start Phase 1 from that tag.


## Phase 0S acceptance ledger — 2026-11-15

### Automated verification

- GitHub Actions run for code commit `10bcda0091280d30863bdd1ebaf82d42b63e6633`: https://github.com/PritPatel845/pie-ai-assientance/actions/runs/43673193185 (push and pull-request runs both passed).
- `pytest -q`: **206 passed**.
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

### Still blocking Phase 0S completion

- `assets/hand_landmarker.task` is committed (7,819,105 bytes). The model-asset workflow downloaded it from Google's official URL and verified SHA-256 `fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1` before committing. `ensure_model()` independently verifies both size and hash at runtime.
- The actual target Mac has not been audited here: `uname -m`, `sw_vers`, Homebrew Python 3.12 path, and imports/versions for MediaPipe 0.10.35 Tasks API, OpenCV, PyAutoGUI, Quartz, and AppKit remain unverified.
- Packaging risk to resolve on the target Mac: PyPI's MediaPipe 0.10.35 metadata advertises a macOS 11+ arm64 wheel, but its dependencies include `opencv-contrib-python`, `sounddevice`, and `matplotlib`; the Phase 0S dependency contract names `opencv-python`. Do not blindly install both OpenCV wheel distributions; determine a compliant, working install strategy on the target Mac and record it before accepting the phase.
- `scripts/manual_checks/audit_macos.command` and `scripts/manual_checks/phase0s.md` have not been run on the target Mac. Camera preview, HUD poses, camera release, Accessibility permission, and safe cursor/pinch behaviour remain unverified.
- macOS-specific media-key behaviour and app automation have not been verified on the target Mac. `play_media()`/`stop_media()` now target an already-running Spotify or Music process via AppleScript and fall back to PyAutoGUI's `playpause` key; CI tests both routing and fallback. The actual key's availability and behaviour still require target-Mac verification.
- Phase 0S is **not accepted**. Do not create `pie-phase-0-done` or begin Phase 1 until the model and Mac/manual acceptance gates are satisfied.
