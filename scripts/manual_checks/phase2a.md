# Phase 2A — local voice manual checks

Run from the repository root on the target Mac. These checks require a microphone and the
optional macOS audio/STT dependencies; CI uses fakes and never opens the microphone.

## 1. Environment and device audit

```bash
cd ~/Downloads/pie-ai-assientance-phase-1
.venv-mac/bin/python -m pip show sounddevice mlx-whisper
.venv-mac/bin/python -c 'import sounddevice as sd; print(sd.query_devices()); print("default:", sd.default.device)'
```

Confirm the intended Mac microphone is selected. In macOS, grant Microphone access to the
host application running Python (Terminal, iTerm, or VS Code).

## 2. Install the local MLX backend

```bash
.venv-mac/bin/python -m pip install '.[mac]'
.venv-mac/bin/python -c 'import mlx_whisper; print("mlx-whisper import OK")'
```

The first actual transcription lazily downloads the configured model into
`~/.pie/models/stt/`. The download is logged; the configured model must remain under 1 GB.
No model download is performed by the test suite.

Run the five-second direct recording/transcription check:

```bash
.venv-mac/bin/python scripts/manual_checks/record_and_transcribe.py --seconds 5
```

## 3. Start and observe voice events

```bash
.venv-mac/bin/python -m pie run --voice-background --print-events
```

Speak naturally and check the event stream:

- `input.voice.wake` appears after saying “Pie”.
- `input.voice.listening` activates for the configured listen window.
- `input.voice.transcript` includes `addressed` and `raw`.
- “Pie open Safari” opens Safari through the legacy rule executor.
- Unaddressed speech is still published with `addressed=false`, but does not execute.
- TTS output is not re-transcribed; the echo guard drops capture while speaking.
- A macOS notification appears with title `PIE ACTIVE`.

For an offline check, download the model first, turn Wi-Fi off, restart PIE, and repeat
“Pie open Safari”. The voice path must not attempt a network connection.

## 4. Permission and privacy checks

- Revoke Microphone permission for the host app, start PIE, and verify a
  `system.error` event explains:
  `System Settings > Privacy & Security > Microphone: enable <host app>`.
- Restore permission and verify capture recovers; after repeated failure the capture thread
  gives up without crashing the daemon.
- With `voice.debug_save_audio=false`, confirm no WAV files are created.
- Only for a deliberate debug run, set `debug_save_audio=true`; confirm a startup WARNING and
  WAV files under `~/.pie/debug_audio/`. Turn it off afterwards.

## 5. Performance measurements

Speak a three-second phrase and measure end-of-speech to transcript latency. Target: <= 1.5 s.
With the microphone open and the room silent, measure idle CPU. Target: < 5%.

Record the Mac model, macOS version, selected input device, backend, model name and on-disk
size, first-download duration, warm transcription latency, end-of-speech latency and idle CPU.
Do not report these measurements as passed until they are measured on the target Mac.
