# Pie roadmap

Build strictly in order. A phase is complete only after its automated acceptance suite, static checks, documented manual checks on the target Mac, and handoff report pass. Each phase uses a dedicated branch and `pie-phase-N-done` tag.

| Phase | Scope | Gate |
|---|---|---|
| 0S | Clean-room foundation: package, gesture classification/game profiles/learning, bounded voice parser, Mac adapter, CLI and tests | Python 3.12, pytest, Ruff, mypy, manual macOS checks |
| 1 | Async event bus, daemon, runtime state, full config, gesture/voice event publication | concurrency, lifecycle, config and compatibility tests |
| 2A | Local VAD, STT, wake gating, TTS | offline end-to-end voice and privacy checks |
| 2B | Deterministic rules, cloud-first brain, local fallback, quota tracking | provider fallback matrix and security tests |
| 3A | Tool registry, schema validation, permission gate, audit, Mac tools | every action through registry; hostile path/security tests |
| 3B | MCP server and client | protocol interoperability and trust-boundary tests |
| 3C | Git, VS Code, coding agents, browser, papers, PPT/project, music | dry-run, URL policy, process safety tests |
| 3D | Blender, MATLAB, Inkscape, AutoCAD, WhatsApp | structured operations and graceful missing-app tests |
| 4 | Game detection, profiles, custom gesture learning | deterministic recorded-input tests and manual game checks |
| 5 | Menu-bar UI, event display, background mode | live event/UI integration tests |
| 6 | Memory, safety hardening, launchd, doctor | persistence, red-team, reboot and permissions verification |

No later phase may silently change the frozen contracts in `docs/CONTRACTS.md`. Any required contract change must be documented as a change request before implementation.
