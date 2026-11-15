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
