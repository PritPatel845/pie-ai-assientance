# Phase 2B — BrainRouter manual checks

Run from the repository root on the target Mac.

## 1. Install optional provider dependencies

```bash
.venv-mac/bin/python -m pip install -e ".[brain]"
```

## 2. Configure cloud credentials without writing secrets to TOML

```bash
.venv-mac/bin/python -m pie brain set-key anthropic
.venv-mac/bin/python -m pie brain set-key openai
```

Set the model identifiers you actually use in `~/.pie/config.toml`. Do not copy model names from source code or commit personal keys.

```toml
[brain]
enabled = true
cloud_order = ["anthropic", "openai"]
cli_providers_enabled = false
anthropic_model = ""
openai_model = ""
local_backend = "auto"
local_model = ""
```

Fill in at least one model identifier. Keep the other blank if that provider is not configured.

## 3. Check provider status and direct provider calls

```bash
.venv-mac/bin/python -m pie brain status
.venv-mac/bin/python -m pie brain test anthropic
.venv-mac/bin/python -m pie brain test openai
```

The status command must report configured state, key presence (never the key), quota state, health result and latency. A CLI provider shown as `stubbed: unsafe to sandbox` is intentionally not executable.

## 4. Test cloud-first routing

```bash
.venv-mac/bin/python -m pie brain ask "what is 2+2"
```

Expected: route and provider are printed, with a concise answer. If no cloud model is configured, status must say so rather than inventing a model identifier.

## 5. Verify local fallback

Start Ollama yourself; PIE must not auto-start it.

```bash
ollama list
.venv-mac/bin/python -m pie brain status
```

With a local model installed and within `local_max_ram_gb`, disconnect Wi-Fi and ask a question through the voice wake flow. Confirm that the cloud failure is followed by a local provider switch and a response. Reconnect Wi-Fi afterward.

For MLX, configure an already-running OpenAI-compatible server using `PIE_MLX_BASE_URL`; PIE does not launch it.

## 6. Verify explicit local, quota, and one-execution handoff

- Say: `Pie use the local model what is the capital of France`. Confirm the cloud providers are skipped.
- Run `pie quota show`; use `pie quota reset all` to clear test state.
- Trigger a cloud quota failure (use a provider test account with a known safe quota condition; do not deliberately spend money). Confirm the exact spoken switch message occurs only for quota fallback.
- Say `Pie open Safari`. Confirm Safari opens once, not twice.
- Say an addressed natural-language question. Confirm one BrainRouter response is spoken.
- Say an unaddressed sentence outside the wake window. Confirm it is not sent to the BrainRouter.
- Type a command by publishing `input.text.command` in an integration harness; confirm the same router path is used.

## 7. Verify safe failure and cancellation

- Temporarily stop Ollama and make cloud providers unavailable. Ask a question; expected result is `No AI model is available right now.`, with `ok=false`.
- While a fake/slow provider request is running in a test harness, send `stop`; the active request should be cancelled.
- Keep `cli_providers_enabled=false` unless the Claude/Codex CLI sandbox flags have been verified and the stubs intentionally replaced.

## 8. Capture measurements

Record provider name, configured model identifier, local model disk size (when available), local response latency, and whether the Mac returned to idle memory after the configured `local_keep_alive` period. Do not record API keys or raw user transcripts.
