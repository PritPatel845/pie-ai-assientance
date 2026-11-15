# PIE CONTRACTS v1 — Phase 0S clean-room adaptation

PROJECT: Pie, a local-first macOS personal assistant. Target: Apple Silicon Mac,
macOS, Python 3.12, single user.

## Non-negotiable rules
1. Verify APIs and platform behaviour before relying on them.
2. Do not change frozen event, tool, provider, or config contracts in later phases.
3. Keep phase changes isolated.
4. Unit tests must not require camera, microphone, network, screen, GUI, or real apps.
5. Use future annotations, type hints, Ruff, and strict mypy.
6. Never put secrets in source, config, tests, or logs.
7. Model output is never executed as shell. Subprocesses use argument lists, shell=False,
   timeouts, and allow-listed executables.
8. Real-world actions must go through the later Tool registry and permission gate.
9. Phase plan and file scope must be documented.
10. Every phase appends a handoff report.
11. Do not hide unresolved failures.
12. No unapproved dependencies or out-of-phase refactors.

## Canonical layout
The clean-room path omits legacy/ and the root jarvis.py shim. Data lives under ~/.pie:
config.toml, state/, logs/, models/, and learning/.

## Frozen event contract (Phase 1)
Event fields: topic, payload, source, ts, id, correlation_id. EventBus publishes from
any thread, has per-subscriber queues of max 1000, supports fnmatch patterns, runs sync
handlers in an executor, awaits async handlers, and isolates failures. Canonical topics
are defined in the project specification and may only be added through a change request.

## Threading
OpenCV windows and AppKit remain on the main thread. The asyncio loop, when introduced,
runs in a dedicated pie-loop thread. Blocking camera, microphone, inference, and subprocess
work must not run on that loop. Shutdown releases keys, camera, audio streams, child
processes, and flushes learning/audit state.

## Configuration
Precedence: packaged defaults, ~/.pie/config.toml, PIE_<SECTION>_<KEY> environment,
then CLI overrides. Unknown keys are errors. Phase 0S keys are [app], [gesture], [voice],
and [ui]. Later phases may only add keys.

## Permission tiers
READ=0, REVERSIBLE=1, CONFIRM=2, BLOCKED=3. CONFIRM requires explicit approval every
time. BLOCKED actions never run.

## Tool contract
ToolSpec has name, description, JSON Schema parameters, tier, timeout_s, and platforms.
ToolResult has ok, JSON-serializable output, optional error, and artifact paths.
ToolRegistry.execute is the only execution path: validate, permission, events, timeout,
audit. Tool implementations do not raise to callers and honor dry_run.

## Brain routing
Deterministic rules first. Explicit local requests use local. Otherwise cloud providers
are tried in configured order; local fallback occurs only when every cloud provider is
quota-exhausted, rate-limited past deadline, unauthenticated, offline, or user explicitly
requests local. Local tools may only call READ/REVERSIBLE tools.

## Phase 0S changes from the generic contract
- Removed legacy/ and root jarvis.py because this is a clean-room build.
- Removed ~/.jarvis_learning migration because no legacy data exists.
- Renamed section 10 to FOUNDATION BEHAVIOUR (specified by Phase 0S).
