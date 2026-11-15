from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

from pie.brain.module import BrainModule
from pie.config import BrainConfig, Config
from pie.events import Event, EventBus
from pie.inputs.voice.executor import LegacyRuleExecutor


class FakeMacController:
    def __init__(self) -> None:
        self.opened: list[str] = []

    def open_application_or_item(self, target: str) -> bool:
        self.opened.append(target)
        return True


def test_brain_module_executes_deterministic_voice_rule_exactly_once(tmp_path: Path) -> None:
    async def scenario() -> None:
        loop = asyncio.get_running_loop()
        bus = EventBus(loop)
        mac = FakeMacController()
        executor = LegacyRuleExecutor(mac)
        daemon = SimpleNamespace(config=Config(brain=BrainConfig()), bus=bus, loop=loop)
        module = BrainModule(executor_getter=lambda: executor)
        module.start(daemon)
        handled = asyncio.Event()

        async def receive(event: Event) -> None:
            if event.topic == "tts.say":
                handled.set()

        bus.subscribe("tts.say", receive, name="brain-module-test")
        bus.publish(
            "input.voice.transcript",
            {"text": "open safari", "raw": "hey pie open safari", "final": True, "addressed": True},
            source="voice",
        )
        await asyncio.wait_for(handled.wait(), timeout=1.0)
        assert mac.opened == ["safari"]
        await asyncio.to_thread(module.stop)

    asyncio.run(scenario())


def test_brain_module_accepts_typed_text_commands(tmp_path: Path) -> None:
    async def scenario() -> None:
        loop = asyncio.get_running_loop()
        bus = EventBus(loop)
        mac = FakeMacController()
        executor = LegacyRuleExecutor(mac)
        daemon = SimpleNamespace(config=Config(brain=BrainConfig()), bus=bus, loop=loop)
        module = BrainModule(executor_getter=lambda: executor)
        module.start(daemon)
        handled = asyncio.Event()

        async def receive(event: Event) -> None:
            if event.topic == "tts.say":
                handled.set()

        bus.subscribe("tts.say", receive, name="brain-text-module-test")
        bus.publish("input.text.command", {"text": "open calculator"}, source="text")
        await asyncio.wait_for(handled.wait(), timeout=1.0)
        assert mac.opened == ["calculator"]
        await asyncio.to_thread(module.stop)

    asyncio.run(scenario())
