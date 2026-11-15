# Phase 1 manual checks (macOS)

Run from the repository root with the project virtual environment active.

1. Confirm config rendering without creating user directories:
   `python -m pie config show`
2. Run the event stream:
   `python -m pie run --print-events`
3. Hold an open palm to arm, then show each supported gesture. Confirm
   `input.gesture.state` arrives at the configured rate (default about 10 Hz), and
   `input.gesture.event` appears once per rising edge rather than every frame.
4. Toggle desktop/game with `g`, then select profiles with `1`, `2`, and `3`.
   Confirm `system.mode` contains the current mode and game profile.
5. Confirm cursor, click, volume, media, and game actions still behave as they did in
   Phase 0S. The event bus is observational only.
6. Press `q` to exit. Confirm the camera indicator turns off and held game keys are released.
7. Run `python -m pie run --voice-background --print-events`, then press Ctrl+C.
   Confirm the process exits promptly. Phase 1 does not yet capture microphone audio; voice
   event publication methods are exercised by unit tests until Phase 2A.
8. Run `pytest -q`, `ruff check .`, `ruff format --check .`, and `mypy src/pie`.

Do not test with real applications or camera in CI. Hardware checks are owner-run and must be
recorded separately from automated test evidence.
