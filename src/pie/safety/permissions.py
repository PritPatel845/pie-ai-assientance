from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass
from enum import IntEnum
from typing import Any

from pie.events import Event, EventBus
from pie.safety.audit import redact


class Tier(IntEnum):
    READ = 0
    REVERSIBLE = 1
    CONFIRM = 2
    BLOCKED = 3


@dataclass(slots=True)
class PermissionDecision:
    allow: bool
    by: str


@dataclass(slots=True)
class _Pending:
    call_id: str
    request_ts: float
    future: asyncio.Future[PermissionDecision]


class PermissionGate:
    """FIFO confirmation gate; consent must arrive after the request exists."""

    _YES = {"yes", "confirm", "approve", "do it", "go ahead"}
    _NO = {"no", "cancel", "stop", "deny", "don't"}

    def __init__(
        self,
        bus: EventBus,
        *,
        timeout_s: float = 20.0,
        max_prompts_per_min: int = 3,
        clock: Any = time.time,
    ) -> None:
        self.bus = bus
        self.timeout_s = timeout_s
        self.max_prompts_per_min = max_prompts_per_min
        self.clock = clock
        self._pending: deque[_Pending] = deque()
        self._prompt_times: deque[float] = deque()
        self._unsubscribers: list[Any] = []
        self._started = False
        self._armed = False
        self._lock = asyncio.Lock()

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        self._unsubscribers = [
            self.bus.subscribe("input.voice.transcript", self._on_voice, name="permission-voice"),
            self.bus.subscribe(
                "input.gesture.*", self._on_gesture_event, name="permission-gesture"
            ),
            self.bus.subscribe("ui.command", self._on_ui, name="permission-ui"),
        ]

    def stop(self) -> None:
        for unsubscribe in self._unsubscribers:
            unsubscribe()
        self._unsubscribers.clear()
        self._started = False

        def cancel_pending() -> None:
            for pending in tuple(self._pending):
                if not pending.future.done():
                    pending.future.set_result(PermissionDecision(False, "shutdown"))
            self._pending.clear()

        if self.bus.loop.is_running() and not self.bus.loop.is_closed():
            self.bus.loop.call_soon_threadsafe(cancel_pending)
        else:
            cancel_pending()

    async def _resolve_oldest(self, event: Event, allow: bool, by: str) -> None:
        async with self._lock:
            if not self._pending:
                return
            pending = self._pending[0]
            if event.ts < pending.request_ts:
                return
            self._pending.popleft()
            if not pending.future.done():
                pending.future.set_result(PermissionDecision(allow, by))
            self.bus.publish(
                "permission.response",
                {"call_id": pending.call_id, "allow": allow, "by": by},
                source="permission_gate",
            )

    async def _on_voice(self, event: Event) -> None:
        payload = event.payload
        if not payload.get("final") or not payload.get("addressed"):
            return
        text = " ".join(str(payload.get("text", "")).casefold().split())
        text = text.strip(" .,!?:;")
        if text in self._YES:
            await self._resolve_oldest(event, True, "voice")
        elif text in self._NO:
            await self._resolve_oldest(event, False, "voice")

    async def _on_gesture_event(self, event: Event) -> None:
        if event.topic == "input.gesture.state":
            self._armed = bool(event.payload.get("armed", False))
            return
        if event.topic != "input.gesture.event" or not self._armed:
            return
        name = event.payload.get("name")
        if name == "thumb_up":
            await self._resolve_oldest(event, True, "gesture")
        elif name == "thumb_down":
            await self._resolve_oldest(event, False, "gesture")

    async def _on_ui(self, event: Event) -> None:
        if event.payload.get("name") != "permission":
            return
        allow = event.payload.get("allow")
        if isinstance(allow, bool):
            await self._resolve_oldest(event, allow, "ui")

    async def request(
        self,
        *,
        call_id: str,
        tool: str,
        args: dict[str, Any],
        tier: Tier,
        prompt: str,
        timeout_s: float | None = None,
        pre_approved_by: str | None = None,
    ) -> PermissionDecision:
        if tier is Tier.BLOCKED:
            return PermissionDecision(False, "blocked")
        if tier <= Tier.REVERSIBLE:
            return PermissionDecision(True, "auto")
        if pre_approved_by:
            return PermissionDecision(True, pre_approved_by)

        now = self.clock()
        while self._prompt_times and now - self._prompt_times[0] >= 60:
            self._prompt_times.popleft()
        if len(self._prompt_times) >= self.max_prompts_per_min:
            self.bus.publish(
                "permission.response",
                {"call_id": call_id, "allow": False, "by": "too_many_confirmations"},
                source="permission_gate",
            )
            return PermissionDecision(False, "too_many_confirmations")
        self._prompt_times.append(now)

        loop = asyncio.get_running_loop()
        future: asyncio.Future[PermissionDecision] = loop.create_future()
        pending = _Pending(call_id, now, future)
        async with self._lock:
            self._pending.append(pending)

        safe_args = redact(args, tool=tool)
        self.bus.publish(
            "permission.request",
            {
                "call_id": call_id,
                "tool": tool,
                "args": safe_args,
                "tier": tier.name,
                "prompt": prompt,
                "timeout_s": timeout_s or self.timeout_s,
            },
            source="permission_gate",
        )
        self.bus.publish(
            "tts.say",
            {
                "text": f"{prompt} Say yes or no, or give a thumbs up or thumbs down.",
                "interrupt": False,
            },
            source="permission_gate",
        )
        try:
            return await asyncio.wait_for(future, timeout_s or self.timeout_s)
        except TimeoutError:
            async with self._lock:
                try:
                    self._pending.remove(pending)
                except ValueError:
                    pass
            self.bus.publish(
                "permission.response",
                {"call_id": call_id, "allow": False, "by": "timeout"},
                source="permission_gate",
            )
            return PermissionDecision(False, "timeout")
        except asyncio.CancelledError:
            async with self._lock:
                try:
                    self._pending.remove(pending)
                except ValueError:
                    pass
            self.bus.publish(
                "permission.response",
                {"call_id": call_id, "allow": False, "by": "cancelled"},
                source="permission_gate",
            )
            raise


__all__ = ["PermissionDecision", "PermissionGate", "Tier"]
