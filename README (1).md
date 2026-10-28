# Jarvis Air Control

This is the real Python controller. It reads the webcam with OpenCV and MediaPipe, maps the index finger to the macOS cursor, and emits native Quartz input events.

## Run

```bash
 /opt/homebrew/bin/python3.12 -m venv .venv
 .venv/bin/python -m pip install -r requirements.txt
 .venv/bin/python jarvis.py --no-actions
.venv/bin/python jarvis.py
 .venv/bin/python jarvis.py --voice
.venv/bin/python jarvis.py --no-voice
```

The first run downloads `hand_landmarker.task`. macOS must grant the terminal or Python process Camera and Accessibility permissions in System Settings > Privacy & Security. Use `--no-actions` first to confirm tracking.

Voice control runs beside hand control by default; use `--no-voice` to disable it. macOS must grant Microphone permission and the recognizer uses Google's speech endpoint for transcription. Say `JR open Safari` in one phrase, or say `JR`, wait for the activation message, then say `open Safari`; activation lasts 10 seconds. `J R`, `J.R.`, `Hey JR`, `Jay R`, and `Jarvis` are also accepted. Say `JR stop listening` to turn voice off while keeping the camera loop running. Other commands include `JR search weather tomorrow`, `JR set volume to 40`, `JR close app`, `JR confirm delete`, `JR copy`, `JR paste`, `JR undo`, `JR type hello`, `JR play`, `JR pause`, `JR mute`, `JR scroll up`, `JR take a screenshot`, and `JR lock screen`. Speech without a wake word is ignored. Use `--no-actions` to test recognition without triggering desktop actions.

## Gestures

- Hold an open palm for two seconds: arm control.
- Index finger: move the cursor.
- Pinch thumb + index, then release: double-click at the current cursor position to open a folder or launch an item.
- Three fingers extended: alternate double-click gesture for opening a folder or launching an item.
- Two-finger horizontal movement: scroll.
- Open palm pushed toward the camera: mute system audio.
- Thumb up: start/toggle the active background music or video.
- Thumb down: stop/pause Music, Spotify, or the system media session.
- Fist: run the command in `JARVIS_VOICE_COMMAND`, for example `export JARVIS_VOICE_COMMAND='python3 local_voice.py'`.
- Hand depth: adjusts system output volume.

Press `q` or `Esc` in the camera window to stop. Keep the camera window visible while calibrating; this version uses hand landmarks and native desktop events. True eye-gaze window selection needs an eye-tracker or a separately calibrated face/eye model, so it is not silently represented as a fake target lock.

The preview opens as a small window in the upper-left so the desktop remains visible. Move the pointer over a desktop folder, pinch and hold briefly, then release to open it. Do not place the preview window over the folder you want to control.

## Game control

Game control is deliberately separate from desktop control. A normal launch starts in desktop mode. Start one profile only after focusing the game:

```bash
.venv/bin/python jarvis.py --game-profile asphalt
.venv/bin/python jarvis.py --game-profile temple-run
.venv/bin/python jarvis.py --game-profile counter-strike --no-actions
```

Hold an open palm for two seconds to arm it. In game mode, normal cursor and media actions are disabled. Press `g` in the camera window to enter the selected game profile; press `g` again to return to desktop mode. The profile controls are:

Press `1`, `2`, or `3` while the camera window is focused to switch profiles live: `1` is Asphalt 8, `2` is Temple Run, and `3` is Counter-Strike 2. Switching profiles releases old keys and resets the arm state, so hold the open palm for two seconds again. Press `g` to switch between desktop mode and the selected game profile. A plain launch uses Asphalt 8 as the default profile; you can also select a profile at launch with `--game-profile temple-run` or `--game-profile counter-strike`.

- `asphalt`: arm with an open palm centered in the camera. Four fingers up holds right and three fingers up holds left with immediate response. Either steering pose accelerates, fist brakes, and pinch triggers nitro. Hold two fingers up and lean left or right to drift; drift also holds the brake.
- `temple-run`: four fingers up turn right, three fingers up turn left, palm up jumps, palm down slides, thumb up jumps, and fist holds slide.
- `counter-strike`: four fingers up strafes right, three fingers up strafes left, steady open palm moves forward, fist moves backward, pinch clicks, and thumb up jumps.

Use `--no-actions` first. These are global keyboard and mouse events, so only run them while the intended game window has focus. Releasing the camera loop releases any held keys.

Steering is highly sensitive by default. Adjust it with `--steer-sensitivity`; lower values respond to smaller movements:

```bash
.venv/bin/python jarvis.py --game-profile asphalt --steer-sensitivity 0.002
```