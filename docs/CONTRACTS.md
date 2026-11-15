# PIE CONTRACTS v1

PROJECT: Pie (the pi symbol), a local-first macOS personal assistant.
Formerly "Jarvis Air Control".
Target machine: MacBook Air, Apple Silicon, 16 GB unified memory, macOS,
Python 3.12, single user.

## 0. Non-negotiable working rules

- **R1 — Verify, never guess.** Verify existing code, library APIs, CLI flags, and macOS behaviour before use. Read files, run `python -c`, run `<tool> --help`, inspect installed package source in the virtual environment, and use `pip show <pkg>` for versions.
- **R2 — Frozen contracts.** Do not change sections 3–8 unless a phase explicitly permits it. If a contract must change, write `docs/CONTRACT_CHANGE_REQUEST.md` and obtain approval.
- **R3 — Minimal blast radius.** Touch only files listed for the active phase. Read an existing file fully before editing.
- **R4 — Tests and fakes.** Every new module has tests. `pytest -q` passes before and after each phase. Unit tests never need camera, microphone, network, screen, GUI, or real apps; fake hardware, OS, and network behind interfaces. Real-hardware checks live in `scripts/manual_checks/` and are documented.
- **R5 — Quality.** Use `from __future__ import annotations`, full type hints, clean `ruff check`, `ruff format`, and clean mypy on new code (or pyright if mypy cannot be installed).
- **R6 — Secrets.** No secrets in code, config, logs, tests, or git. API keys come from macOS Keychain (`keyring`, service name `pie`) or environment variables. Log only whether a key is present.
- **R7 — Process safety.** Model output is never executed as shell. Subprocesses use argument lists (`shell=False`), a timeout, and an allow-listed executable.
- **R8 — Action safety.** Anything that acts on the real world goes through the Tool registry and permission gate (sections 6 and 7). No model output reaches MacController-style code any other way.
- **R9 — Plan first.** Before writing code, post files to create/modify/not touch, risks, test plan, and ambiguities; wait for the user's go-ahead.
- **R10 — Handoff.** Finish with a Handoff Report appended to `docs/HANDOFF.md`: what was built, public symbols, config keys, event topics, limitations, exact verify commands, and what the next phase must know.
- **R11 — Failures.** If an error is not fixed after two attempts, stop and report what was tried. Never hide failures with broad try/except. Log with context and publish `system.error`.
- **R12 — Scope and dependencies.** No extra features, refactors outside listed files, or dependencies outside the phase's allowed list. Pin versions in `pyproject.toml`.

## 1. Canonical repository layout

```text
pie/
  pyproject.toml                  # package name pie; Python >=3.12,<3.13
  README.md
  docs/{HANDOFF.md, CONTRACTS.md, ARCHITECTURE.md}
  config/pie.default.toml
  assets/hand_landmarker.task
  legacy/                         # original Jarvis files, untouched
  scripts/{start_pie.command, manual_checks/}
  src/pie/
    __init__.py __main__.py version.py config.py paths.py logging_setup.py
    events.py
    core/{daemon.py, state.py}
    inputs/gesture/{features.py, engine.py, runner.py, game.py, learning.py}
    inputs/voice/{commands.py, executor.py, vad.py, stt.py, wake.py, tts.py, pipeline.py}
    inputs/text.py
    brain/{types.py, router.py, rules.py, quota.py,
           providers/{base,anthropic_api,openai_api,claude_cli,codex_cli,local}.py}
    tools/{base.py, registry.py, builtin/, mcp/{server.py, client.py}}
    safety/{permissions.py, audit.py}
    platform/mac.py
    memory/store.py
    ui/{server.py, static/}
  tests/
  jarvis.py                       # temporary shim; removed in phase 6
```

## 2. Data locations

- `~/.pie/config.toml`: user overrides.
- `~/.pie/state/`: runtime state (for example `quota.json`).
- `~/.pie/logs/`: rotating logs.
- `~/.pie/models/`: downloaded models.
- `~/.pie/learning/`: gesture/voice data. Migration from `~/.jarvis_learning` is COPY only; never move or delete the old folder.

## 3. Events — frozen API (`src/pie/events.py`)

`Event` is a frozen, slotted dataclass with:
- `topic: str`
- `payload: Mapping[str, Any]`
- `source: str`
- `ts: float` (time.time())
- `id: str` (uuid4().hex)
- `correlation_id: str | None = None`

`EventBus` contract:
- `EventBus(loop: asyncio.AbstractEventLoop)`
- `publish(topic, payload=None, *, source, correlation_id=None) -> Event`: thread-safe and non-blocking; callable from any thread.
- `subscribe(pattern, handler, *, name) -> Callable[[], None]`: fnmatch patterns such as `input.voice.*`; sync handlers run in an executor; async handlers are awaited. Returns an unsubscribe function.
- `wait_for(pattern, *, timeout, predicate=None) -> Event`.
- One queue per subscriber, maximum size 1000. On overflow drop the oldest event and publish `system.warning`, rate-limited to once per 5 seconds; never publish overflow warnings for topics beginning `system.`.
- A raising handler is logged, publishes `system.error`, and never affects other handlers.

Canonical topics and payload keys (new topics must be added here first):

| Topic | Payload keys |
|---|---|
| `system.started` | `version` |
| `system.stopping` | none |
| `system.error` | `where, error, detail` |
| `system.warning` | `where, message` |
| `system.mode` | `mode: desktop\|game\|idle, game_profile?` |
| `input.gesture.state` | `hands, gesture, depth, armed, fps` — at most 10 Hz, never per frame |
| `input.gesture.event` | `name, hand, confidence` |
| `input.voice.wake` | `word` |
| `input.voice.listening` | `active, until` |
| `input.voice.transcript` | `text, final, lang`; Phase 2A adds `addressed: bool, raw: str` |
| `input.text.command` | `text` |
| `intent.resolved` | `text, route: rule\|cloud\|local, provider?` |
| `brain.request` | `request_id, text, provider` |
| `brain.delta` | `request_id, text` |
| `brain.response` | `request_id, text, provider, usage?` |
| `brain.provider.switched` | `from, to, reason: quota\|rate_limit\|offline\|user_request\|error` |
| `brain.quota` | `provider, exhausted_until` |
| `tool.requested` | `call_id, tool, args, tier` |
| `tool.approved` | `call_id, by: auto\|user` |
| `tool.denied` | `call_id, reason` |
| `tool.started` | `call_id` |
| `tool.finished` | `call_id, ok, summary, duration_s` |
| `permission.request` | `call_id, tool, args, tier, prompt, timeout_s` |
| `permission.response` | `call_id, allow, by: voice\|gesture\|ui\|timeout` |
| `ui.client.connected` | `count` |
| `ui.command` | `name, args` |
| `tts.say` | `text, interrupt` |

## 4. Threading model — frozen

- macOS requires OpenCV windows (`cv2.imshow` / `cv2.waitKey`) and AppKit on the main thread.
- The asyncio loop runs in a dedicated thread named `pie-loop`. The main thread runs the camera/GUI loop when the preview window is on; otherwise it blocks on a `threading.Event`.
- Blocking work (camera read, mic read, STT, model inference, subprocess) never runs on the loop thread: use dedicated threads, `asyncio.to_thread`, or asyncio subprocess.
- Cross-thread communication uses only `EventBus.publish` and `loop.call_soon_threadsafe`.
- Shutdown uses one `threading.Event` named `stop`. Every thread loop checks it at least every 200 ms. On stop: release held game keys, release camera, close audio streams, terminate child processes, flush audit log and learning data.

## 5. Configuration — frozen

Loader uses `tomllib`. Precedence:
`config/pie.default.toml < ~/.pie/config.toml < PIE_<SECTION>_<KEY> environment < CLI flags`.

The result is a frozen `Config` dataclass with frozen nested dataclasses. Unknown keys are errors that name the key. Existing keys are never renamed; later phases only add keys. Public loader: `load_config(cli_overrides: Mapping | None = None) -> Config`.

| Section | Keys and defaults |
|---|---|
| `[app]` | `name='pie'`, `log_level='INFO'` |
| `[gesture]` | `camera=0`, `preview=true`, `arm_hold_seconds=2.0`, `steer_sensitivity=0.004`, `state_hz=10`, `model_path=''` (empty = `assets/hand_landmarker.task`, then `~/.pie/models`, then download) |
| `[voice]` | `enabled=true`, `wake_words=['pie','hey pie','pi','jr','j r','jay r','jarvis']`, `listen_seconds=20`, `language='en'`, `stt_backend='auto'`, `stt_model='base.en'`, `input_device=''`, `vad_threshold=0.015`, `vad_min_speech_ms=150`, `vad_end_silence_ms=600`, `vad_max_utterance_s=12`, `stt_idle_unload_s=300`, `tts_enabled=true`, `tts_voice='Samantha'`, `tts_rate=185`, `allow_cloud_stt=false`, `debug_save_audio=false` (Phase 2A additions) |
| `[ui]` | `host='127.0.0.1'`, `port=8765` |
| `[brain]` (Phase 2B) | `enabled=true`, `cloud_order=['anthropic','openai']`, `cli_providers_enabled=false`, `anthropic_model=''`, `openai_model=''`, `local_backend='auto'` (`auto\|ollama\|mlx`), `local_model=''`, `max_steps=8`, `total_timeout_s=90`, `provider_timeout_s=45`, `context_turns=6`, `context_ttl_s=600`, `default_cooldown_s=3600`, `rate_limit_max_wait_s=8`, `local_max_ram_gb=6.0`, `local_keep_alive='2m'` |
| Later phases | `[brain]`, `[safety]`, `[tools]` and other phase-owned keys are additive only. |

## 6. Permission tiers — frozen

- `READ=0`: no side effects.
- `REVERSIBLE=1`: easy to undo; examples: open app, volume, screenshot, create a file inside the sandbox directory.
- `CONFIRM=2`: explicit approval every time; examples: send message/call, git push, delete or overwrite a user file, close an app, type text into other apps, spend money, any third-party POST.
- `BLOCKED=3`: never runs; examples: sudo, `rm -rf`, disk format, reading credentials/Keychain/SSH keys.

## 7. Tool contract — frozen (`src/pie/tools/base.py`)

- `ToolSpec` (frozen dataclass): `name` (lowercase `domain.verb`, characters `[a-z0-9_.]`), `description`, `parameters` (JSON Schema object, `additionalProperties: false`), `tier: Tier`, `timeout_s: float = 30.0`, `platforms: tuple[str, ...] = ('darwin',)`.
- `ToolResult` (dataclass): `ok: bool`, JSON-serialisable `output: Any`, optional `error: str | None`, `artifacts: list[str] = []` (absolute paths).
- `Tool` protocol: `spec: ToolSpec`; `async run(args: Mapping[str, Any], ctx: ToolContext) -> ToolResult`.
- `ToolContext`: `config`, `bus`, `cancel: asyncio.Event`, `call_id`, `workdir: Path`, `dry_run: bool`.
- Arguments are validated against the schema before `run()`. `run()` never raises to its caller; it returns `ToolResult(ok=False, error=...)`. Every tool honours `ctx.dry_run` (perform everything except the side effect); long tools check `ctx.cancel`.
- `ToolRegistry`: `register(tool)`, `get(name)`, `list()`, `execute(name, args, *, source, correlation_id)`.
- `execute()` is the only execution path: validate → permission gate → tool events → run with timeout → audit record.

## 8. Brain contract — frozen (`src/pie/brain/`)

- `Message(role: system|user|assistant|tool, content, tool_call_id?, tool_calls?)`
- `ToolCall(id, name, args)`
- `Provider` protocol: `name: str`, `kind: Literal['cloud','local']`; async `complete(messages, tools: list[ToolSpec], *, max_tokens, timeout_s) -> ProviderReply`; async `healthcheck() -> bool`.
- `ProviderReply(text, tool_calls, usage | None, stop_reason)`.
- Errors: `ProviderError`, `QuotaExhausted(provider, reset_at | None)`, `RateLimited(provider, retry_after)`, `ProviderUnavailable(provider)`, `AuthError(provider)`.

Routing policy (do not alter):
1. Deterministic rules (`brain/rules.py`) first. A match runs tools directly with zero model calls.
2. If the utterance explicitly asks for local (`use local`, `locally`, `offline`, `local model`, `without internet`), use the local provider.
3. Otherwise try cloud providers in config order. The local model is used only when every cloud provider is quota-exhausted, rate-limited past its deadline, unauthenticated, or offline, or when rule 2 applies.
4. On `QuotaExhausted`, persist state to `~/.pie/state/quota.json` until `reset_at` or a default cool-down; publish `brain.quota` and `brain.provider.switched`.
5. One user command = one agent run: tool-use loop with `max_steps` (default 8) and a total timeout. No background re-prompting.
6. The local model may only call tools with tier <= `REVERSIBLE`; anything higher needs the permission gate to approve.

## 9. macOS facts to verify

TCC permissions attach to the executable that runs Python (Terminal, iTerm, VS Code, or the venv's Python). Required permissions may include Camera, Microphone, Accessibility (synthetic input), Screen Recording (screenshots), and Automation (AppleScript controlling other apps). A LaunchAgent has its own identity; Phase 6 handles it.

## 10. Existing behaviour to preserve

- Arm by holding an open palm for 2 seconds. Index finger moves the cursor. Pinch (distance/hand size < 0.48) = double click, 0.7-second debounce. Three fingers = double click. Two-finger horizontal move = scroll. Open palm with z < -0.12 = mute. Fist = run `JARVIS_VOICE_COMMAND`. Thumb up = play; thumb down = stop. Hand depth z → volume = clamp(72 - z*180, 0, 100).
- Voice: wake word followed by a bounded command set (`parse_voice_command`); never arbitrary shell.
- Games: profiles `asphalt`, `temple-run`, `counter-strike`; keys 1/2/3 switch; `g` toggles.
- CLI flags: `--camera`, `--no-actions`, `--game-profile`, `--steer-sensitivity`, `--voice/--no-voice`, `--voice-background`, `--learning-dir`, `--voice-listen-seconds`.
- `mediapipe==0.10.35` stays pinned.

---

This file is the authoritative contract. Later phases read it first. Any required change to frozen sections 3–8 must be proposed in `docs/CONTRACT_CHANGE_REQUEST.md` and approved before implementation.
