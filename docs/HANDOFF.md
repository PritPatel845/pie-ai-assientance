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
- Target Mac environment audit has not been run: arm64, macOS version, Homebrew Python 3.12,
  and MediaPipe 0.10.35 Tasks API must be checked on the actual Mac.
- Hand model has not yet been downloaded/committed; no SHA-256 recorded.
- Phase 0S test suite has not yet passed CI. Frame processor game sequences and predicate
  boundaries need broader tests. Runner cleanup needs a fake-capture failure test.
- Script executable bit is not verified via GitHub contents API.
- Real camera preview, HUD, permission flow and safe action test require manual Mac checks.
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
1. Get Python 3.12 CI green, fix all failures.
2. Expand acceptance tests, run strict mypy and Ruff.
3. Verify model download size and SHA-256; add the model only after verification.
4. Run manual hardware checks on the target Mac.
5. Only after every gate passes, tag Phase 0S and start Phase 1 from that tag.


## Phase 0S acceptance ledger — 2026-11-15

### Automated verification

- GitHub Actions run for code commit `03fb6ba5cd0af72eceb87c9b868b6dc896d04a8c`: https://github.com/PritPatel845/pie-ai-assientance/actions/runs/43670182660
- `pytest -q`: **151 passed**.
- `ruff check .`: passed.
- `ruff format --check .`: passed.
- `mypy src/pie`: passed; no issues in 20 source files.
- `python -m pie doctor`: exited successfully on the CI runner.
- CI is Linux/Python 3.12. It is not evidence of macOS/Apple Silicon or camera/permission compatibility.
- `scripts/start_pie.command` Git mode verified as `100755` after commit `21ce135253450391fe6e293363a1181ba1a3c47b`.

### Configuration reference

| Section | Keys | Defaults |
|---|---|---|
| `[app]` | `name`, `log_level` | `pie`, `INFO` |
| `[gesture]` | `camera`, `preview`, `arm_hold_seconds`, `steer_sensitivity`, `state_hz`, `model_path` | `0`, `true`, `2.0`, `0.004`, `10`, `""` |
| `[voice]` | `enabled`, `wake_words`, `listen_seconds`, `language` | `true`, `["pie","hey pie","pi","jr","j r","jay r","jarvis"]`, `20`, `"en"` |
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
- Counter-Strike `KeyAction` names resolve through the selected profile to A/D/W/S keycodes.
- Temple Run handles swipe left/right and palm up/down actions.
- Runner/fist/pinch and game-key state reset on hand loss/mode changes; held keys are released.
- Clean-room Path B no longer copies `~/.jarvis_learning`.
- Config environment parsing, strict unknown-key checks, and CLI-over-config precedence are covered by regression tests.
- Ruff CI is read-only; it never formats and pushes commits from a pull-request merge checkout.
- `FrameProcessor` action-list annotations satisfy strict mypy.
- The voice parser now has a 90-row phrase matrix plus punctuation-boundary wake-word tests.
- Model path resolution and explicit downloads verify the pinned byte size and SHA-256; invalid or partial downloads are removed.
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

- `assets/hand_landmarker.task` is not in the repository. The canonical Google-hosted float16/1 model is pinned in code at **7,819,105 bytes**, SHA-256 `fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1`. The expected size/hash are corroborated by [model metadata](https://github.com/kiya0908/gesture-synth-weld/blob/main/mediapipe-version.json) and [the upstream MediaPipe issue](https://github.com/google-ai-edge/mediapipe/issues/6293). `ensure_model()` now verifies both before accepting or installing a model and removes partial/invalid downloads. The actual binary download still failed in this environment, so no local file has yet been independently hashed or committed.
- The actual target Mac has not been audited here: `uname -m`, `sw_vers`, Homebrew Python 3.12 path, and imports/versions for MediaPipe 0.10.35 Tasks API, OpenCV, PyAutoGUI, Quartz, and AppKit remain unverified.
- `scripts/manual_checks/phase0s.md` has not been performed on the target Mac. Camera preview, HUD poses, camera release, Accessibility permission, and safe cursor/pinch behaviour remain unverified.
- macOS-specific media-key behaviour and app automation have not been verified on the target Mac.
- Phase 0S is **not accepted**. Do not create `pie-phase-0-done` or begin Phase 1 until the model and Mac/manual acceptance gates are satisfied.
