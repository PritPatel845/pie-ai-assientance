from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from pie.events import EventBus
from pie.safety.permissions import Tier
from pie.tools.base import ToolContext
from pie.tools.builtin.filesystem import build_filesystem_tools
from pie.tools.builtin.mac import build_mac_tools
from pie.tools.builtin.media import build_media_tools
from pie.tools.builtin.system import build_system_tools
from pie.tools.builtin.voice import build_voice_tools


class FakeController:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.frontmost = "Finder"

    def frontmost_app(self) -> str:
        return self.frontmost

    def open_application_or_item(self, name: str) -> bool:
        self.calls.append(("open_app", name))
        return True

    def open_target(self, target: str) -> bool:
        self.calls.append(("open_target", target))
        return True

    def set_volume(self, value: int) -> bool:
        self.calls.append(("volume", value))
        return True

    def mute(self) -> bool:
        self.calls.append(("mute", True))
        return True

    def screenshot_to(self, path: str | Path) -> bool:
        self.calls.append(("screenshot", str(path)))
        return True

    def scroll(self, amount: int) -> bool:
        self.calls.append(("scroll", amount))
        return True

    def key_combo(self, *keys: str) -> bool:
        self.calls.append(("keys", keys))
        return True

    def lock_screen(self) -> bool:
        self.calls.append(("lock", True))
        return True

    def close_frontmost(self) -> bool:
        self.calls.append(("close", self.frontmost))
        return True

    def delete_selected(self) -> bool:
        self.calls.append(("delete", True))
        return True

    def type_text(self, text: str) -> bool:
        self.calls.append(("type", text))
        return True

    def play_media(self) -> bool:
        self.calls.append(("play", True))
        return True

    def stop_media(self) -> bool:
        self.calls.append(("pause", True))
        return True


def _context(tmp_path: Path) -> ToolContext:
    loop = asyncio.get_running_loop()
    return ToolContext(
        config=None,
        bus=EventBus(loop),
        cancel=asyncio.Event(),
        call_id="test-call",
        workdir=tmp_path,
    )


def test_builtin_tool_catalog_has_expected_tiers() -> None:
    async def scenario(tmp_path: Path) -> None:
        controller = FakeController()
        tools = [
            *build_system_tools(controller),
            *build_filesystem_tools(),
            *build_mac_tools(controller),
            *build_media_tools(controller),
            *build_voice_tools(EventBus(asyncio.get_running_loop())),
        ]
        catalog = {tool.spec.name: tool.spec for tool in tools}
        assert {
            "system.time",
            "mac.frontmost_app",
            "fs.list_dir",
            "fs.read_text",
            "fs.write_text",
            "mac.open_app",
            "mac.open_url",
            "mac.open_path",
            "browser.search",
            "mac.set_volume",
            "mac.mute",
            "mac.screenshot",
            "mac.scroll",
            "mac.key_combo",
            "mac.lock_screen",
            "mac.close_app",
            "mac.delete_selected",
            "mac.type_text",
            "media.play",
            "media.pause",
            "voice.stop_listening",
        } <= set(catalog)
        assert catalog["mac.close_app"].tier is Tier.CONFIRM
        assert catalog["mac.delete_selected"].tier is Tier.CONFIRM
        assert catalog["mac.type_text"].tier is Tier.CONFIRM
        assert catalog["fs.write_text"].tier is Tier.REVERSIBLE

    asyncio.run(scenario(Path(".")))


def test_mac_open_url_rejects_non_http_schemes(tmp_path: Path) -> None:
    async def scenario() -> None:
        controller = FakeController()
        tools = {tool.spec.name: tool for tool in build_mac_tools(controller)}
        result = await tools["mac.open_url"].run({"url": "javascript:alert(1)"}, _context(tmp_path))
        assert not result.ok
        assert controller.calls == []

    asyncio.run(scenario())


def test_mac_open_app_does_not_accept_paths_or_urls(tmp_path: Path) -> None:
    async def scenario() -> None:
        controller = FakeController()
        tools = {tool.spec.name: tool for tool in build_mac_tools(controller)}
        result = await tools["mac.open_app"].run({"name": "/etc/passwd"}, _context(tmp_path))
        assert not result.ok
        assert controller.calls == []

    asyncio.run(scenario())


def test_mac_type_text_rejects_control_characters(tmp_path: Path) -> None:
    async def scenario() -> None:
        controller = FakeController()
        tools = {tool.spec.name: tool for tool in build_mac_tools(controller)}
        tool = tools["mac.type_text"]
        validator = Draft202012Validator(tool.spec.parameters)

        for value in ("hello\nworld", "test\x1b", "first\tsecond", "nul\x00", "delete\x7f"):
            assert list(validator.iter_errors({"text": value}))

        assert not list(validator.iter_errors({"text": "ordinary typing text"}))
        for value in ("hello\nworld", "test\x1b", "first\tsecond"):
            result = await tool.run({"text": value}, _context(tmp_path))
            assert not result.ok
        assert controller.calls == []

    asyncio.run(scenario())


def test_close_app_prompt_names_and_rechecks_frontmost_application(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        controller = FakeController()
        tool = next(
            item for item in build_mac_tools(controller) if item.spec.name == "mac.close_app"
        )
        prompt = tool.confirmation_prompt({}, "call-1")
        assert prompt is not None and "Finder" in prompt
        ctx = _context(tmp_path)
        ctx.call_id = "call-1"
        controller.frontmost = "Safari"
        result = await tool.run({}, ctx)
        assert not result.ok
        assert not any(name == "close" for name, _ in controller.calls)

    asyncio.run(scenario())


def test_filesystem_write_and_read_utf8_text(tmp_path: Path) -> None:
    async def scenario() -> None:
        root = tmp_path / "sandbox"
        root.mkdir()
        tools = {tool.spec.name: tool for tool in build_filesystem_tools()}
        path = root / "notes.txt"
        ctx = _context(tmp_path)
        written = await tools["fs.write_text"].run({"path": str(path), "content": "Pie notes"}, ctx)
        assert written.ok
        assert path.read_text(encoding="utf-8") == "Pie notes"
        read = await tools["fs.read_text"].run({"path": str(path)}, ctx)
        assert read.ok and read.output == "Pie notes"

    asyncio.run(scenario())


def test_filesystem_read_rejects_binary_data(tmp_path: Path) -> None:
    async def scenario() -> None:
        path = tmp_path / "binary.bin"
        path.write_bytes(b"\xff\xfe\x00")
        tools = {tool.spec.name: tool for tool in build_filesystem_tools()}
        result = await tools["fs.read_text"].run({"path": str(path)}, _context(tmp_path))
        assert not result.ok
        assert result.error == "file is not valid UTF-8 text"

    asyncio.run(scenario())


def test_voice_stop_listening_uses_existing_event_topic(tmp_path: Path) -> None:
    async def scenario() -> None:
        bus = EventBus(asyncio.get_running_loop())
        received = []
        bus.subscribe("input.voice.listening", received.append, name="voice-stop-test")
        await asyncio.sleep(0)
        tool = build_voice_tools(bus)[0]
        result = await tool.run({}, _context(tmp_path))
        await asyncio.sleep(0.01)
        assert result.ok
        assert len(received) == 1
        assert received[0].source == "tool"
        assert received[0].payload["active"] is False

    asyncio.run(scenario())


def test_mac_open_url_rejects_credentials_and_whitespace(tmp_path: Path) -> None:
    async def scenario() -> None:
        controller = FakeController()
        tools = {tool.spec.name: tool for tool in build_mac_tools(controller)}
        for url in (
            "https://user:password@example.com",
            "https://example.com/a b",
        ):
            result = await tools["mac.open_url"].run({"url": url}, _context(tmp_path))
            assert not result.ok
        assert controller.calls == []

    asyncio.run(scenario())


def test_mac_open_app_rejects_control_characters(tmp_path: Path) -> None:
    async def scenario() -> None:
        controller = FakeController()
        tools = {tool.spec.name: tool for tool in build_mac_tools(controller)}
        result = await tools["mac.open_app"].run({"name": "Safari\nTerminal"}, _context(tmp_path))
        assert not result.ok
        assert controller.calls == []

    asyncio.run(scenario())
