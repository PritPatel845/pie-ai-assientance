# Pie architecture

Phase 0S is a hardware-optional foundation. Pure gesture classification and frame-state
processing live under inputs/gesture and return typed actions. Platform effects are
isolated behind MacController. The camera runner owns OpenCV and MediaPipe resources
on the main thread. Voice phrase parsing is pure; VoiceController delegates to a
rule executor and has no microphone capture until Phase 2A.

No event bus, daemon, LLM, cloud provider, tool registry, or UI is part of Phase 0S.
