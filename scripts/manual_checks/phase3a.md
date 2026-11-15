# Phase 3A — Safe tool registry manual checks

Run from the repository root on the target Mac after installing the current branch.

## 1. Verify tool catalogue and CLI parsing

```bash
.venv-mac/bin/python -m pie tool list
.venv-mac/bin/python -m pie tool run system.time --dry-run
.venv-mac/bin/python -m pie audit tail -n 20
```

Expected:
- The catalogue contains the built-in tools listed in `docs/CONTRACTS.md`.
- Dry-run returns a `dry_run=true` result and does not call the tool function.
- Audit tail prints JSONL records; secret values and typed text contents are redacted.

## 2. Verify filesystem boundaries

Create the sandbox test directory:

```bash
mkdir -p ~/PieWorkspace
```

List a directory inside the configured allowed roots:

```bash
.venv-mac/bin/python -m pie tool run fs.list_dir --args-json '{"path":"~/PieWorkspace"}'
```

Create a new file inside the sandbox (no confirmation should be needed):

```bash
.venv-mac/bin/python -m pie tool run fs.write_text --args-json '{"path":"~/PieWorkspace/phase3a-test.txt","content":"Pie Phase 3A test"}'
```

Repeat the write to the same file. Pie must request confirmation. Say yes; then verify the file changed. Say no on a second attempt; verify the file did not change.

Try a write outside the sandbox but within an allowed folder, for example `~/Documents/phase3a-test.txt`. Pie must request confirmation.

Try to read or write each protected target. Every attempt must be rejected without a confirmation prompt:

- `~/.ssh/id_rsa`
- `~/.aws/credentials`
- `~/.gnupg/private-keys-v1.d/`
- `~/Library/Keychains/`
- `~/.pie/config.toml`
- `~/.env` and project `.env` files
- `~/.pie/logs/audit.jsonl`

Also test a symlink inside `~/PieWorkspace` that points to one of those protected locations. The resolved target must be rejected.

## 3. Verify confirmation behaviour

Run the following only when it is safe to perform the corresponding action:

- `mac.close_app`: confirmation must name the currently frontmost app. Switch apps before saying yes; Pie must refuse because the frontmost app changed.
- `mac.delete_selected`: Pie must ask before using the delete shortcut.
- `mac.type_text`: Pie must ask before typing. Newline, escape, and other control characters must be rejected.
- `fs.write_text`: existing files and paths outside the sandbox require a fresh confirmation for every call.
- Speak an unaddressed `yes`; it must not approve anything.
- Speak `yes` before a request; the stale consent must not be reused.
- Let a confirmation time out; the operation must be denied.
- Send four confirmation requests within one minute; requests over the configured limit must be denied.

## 4. Verify deterministic voice routing

With Ollama available, use the normal wake-word flow:

- `Pie open Safari`
- `Pie search weather forecast`
- `Pie play music`
- `Pie pause music`
- `Pie mute`
- `Pie stop listening`
- `Pie delete it`: must ask for confirmation.
- `Pie confirm delete`: explicit confirmation phrase may pre-approve the delete tool.
- `Pie close app`: prompt must name the frontmost application.

Verify that deterministic commands use the same registry and produce tool events and audit records. No model-generated or environment-provided shell command may execute.

## 5. Verify gesture bindings

- While unarmed, thumb-up, thumb-down, and palm-push must not invoke tools.
- Hold an open palm for two seconds to arm.
- Thumb-up invokes the configured `media.play` binding.
- Thumb-down invokes `media.pause`.
- Palm-push invokes `mac.mute`.
- Repeated held gestures must not spam actions.
- Cursor movement, click, scroll, volume-from-depth, and held game keys must retain their existing direct behaviour.
- The legacy environment-provided voice command must not execute.

## 6. Verify safety modes and shutdown

- Start Pie with `--no-actions`; all tool requests must be dry-run only.
- Set `tools.dry_run=true`; no tool implementation may run.
- Add a tool name to `tools.disabled`; the registry must reject it.
- Stop Pie while a confirmation is pending; it must deny the pending request and shut down cleanly.
- Confirm `~/.pie/logs/audit.jsonl` exists with mode `0600`, rotates at 5 MB, and never contains raw `mac.type_text` text or `fs.write_text` content.
