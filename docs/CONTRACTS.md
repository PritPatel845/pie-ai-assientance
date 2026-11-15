# Pie runtime contracts

## Runtime and platform
- Supported target: macOS on Apple Silicon, Python >=3.12,<3.13.
- Core runtime modules must be importable and unit-testable without camera, microphone, GUI, network, or model downloads.
- No model-generated shell execution. OS interaction belongs behind explicit platform/tool adapters.
- Configuration is read-only on load: loading it never creates directories or writes files.

## Event bus (Phase 1)
- Topics are case-sensitive strings matched with fnmatchcase patterns.
- Each subscriber receives its own bounded FIFO queue (default capacity 1000); a slow subscriber cannot block another subscriber.
- Publishing is safe from any thread and schedules delivery with loop.call_soon_threadsafe.
- Overflow drops the oldest queued event and logs a rate-limited warning; system.* events do not generate overflow warnings.
- Async handlers are awaited; synchronous handlers run in the default executor.
- Handler exceptions are isolated and logged; non-system handler failures emit system.error.
- Closing cancels subscriber tasks. Publishing after close or loop shutdown is ignored.

## State and daemon (Phase 1)
- Stop requests are thread-safe and idempotent.
- Runtime state snapshots are created while holding a lock.
- The daemon owns one event loop thread named pie-loop.
- Modules start in registration order and stop in reverse order. Partial startup failure rolls back modules already started.
- Shutdown is bounded; module shutdown failures are logged and do not prevent later modules from stopping.

## Configuration (Phase 1)
- Dataclass configuration objects are frozen.
- Precedence: built-in defaults, optional user TOML, then supported environment overrides.
- Unknown TOML sections/keys and type mismatches are errors.
- Boolean environment values are exactly true or false (case-insensitive).
- Paths are expanded with ~; loading does not create directories.
