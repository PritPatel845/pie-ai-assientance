from __future__ import annotations

import asyncio
import importlib
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, urlsplit

from pie.platform.mac import MacController
from pie.safety.permissions import Tier
from pie.tools.base import FunctionTool, ToolContext, ToolResult, ToolSpec, fail, ok


def _empty_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    }


def build_mac_tools(controller: MacController) -> list[FunctionTool]:
    confirmed_apps: dict[str, str] = {}

    async def open_app(args: Mapping[str, Any], ctx: ToolContext) -> ToolResult:
        name = str(args["name"]).strip()
        if "://" in name or name.startswith(("/", "~", ".")):
            return fail("use mac.open_url or mac.open_path for URLs and paths")
        if ctx.dry_run:
            return ok({"would_open": name})
        opened = await asyncio.to_thread(controller.open_application_or_item, name)
        return ok({"opened": name}) if opened else fail("application could not be opened")

    async def open_url(args: Mapping[str, Any], ctx: ToolContext) -> ToolResult:
        url = str(args["url"]).strip()
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return fail("only valid http and https URLs are allowed")
        if ctx.dry_run:
            return ok({"would_open": url})
        opened = await asyncio.to_thread(controller.open_target, url)
        return ok({"opened": url}) if opened else fail("URL could not be opened")

    async def open_path(args: Mapping[str, Any], ctx: ToolContext) -> ToolResult:
        path = str(args["path"])
        if ctx.dry_run:
            return ok({"would_open": path})
        opened = await asyncio.to_thread(controller.open_target, path)
        return ok({"opened": path}) if opened else fail("path could not be opened")

    async def search(args: Mapping[str, Any], ctx: ToolContext) -> ToolResult:
        query = str(args["query"]).strip()
        url = "https://www.google.com/search?q=" + quote_plus(query)
        if ctx.dry_run:
            return ok({"would_open": url})
        opened = await asyncio.to_thread(controller.open_target, url)
        return ok({"opened": url}) if opened else fail("browser search could not be opened")

    async def set_volume(args: Mapping[str, Any], ctx: ToolContext) -> ToolResult:
        value = int(args["value"])
        if ctx.dry_run:
            return ok({"would_set_volume": value})
        changed = await asyncio.to_thread(controller.set_volume, value)
        return ok({"volume": value}) if changed else fail("volume change failed")

    async def mute(args: Mapping[str, Any], ctx: ToolContext) -> ToolResult:
        del args
        if ctx.dry_run:
            return ok({"would_mute": True})
        changed = await asyncio.to_thread(controller.mute)
        return ok({"muted": True}) if changed else fail("mute failed")

    async def screenshot(args: Mapping[str, Any], ctx: ToolContext) -> ToolResult:
        del args
        filename = (
            Path.home()
            / "Desktop"
            / f"Pie Screenshot {datetime.now():%Y-%m-%d %H-%M-%S}.png"
        )
        if ctx.dry_run:
            return ok({"would_save": str(filename)})
        captured = await asyncio.to_thread(controller.screenshot_to, filename)
        if not captured or not filename.is_file():
            return fail("screenshot failed; check Screen Recording permission")
        try:
            image_module = importlib.import_module("PIL.Image")
            stat_module = importlib.import_module("PIL.ImageStat")
            with image_module.open(filename) as image:
                deviation = stat_module.Stat(image.convert("RGB")).stddev
            if all(value < 0.01 for value in deviation):
                return ToolResult(
                    False,
                    output={"path": str(filename)},
                    error="Screen Recording permission is probably missing",
                    artifacts=[str(filename)],
                )
        except (ImportError, OSError):
            return fail(
                "screenshot captured but image validation was unavailable",
                output={"path": str(filename)},
            )
        return ok({"path": str(filename)}, artifacts=[str(filename)])

    async def scroll(args: Mapping[str, Any], ctx: ToolContext) -> ToolResult:
        amount = int(args["amount"])
        if ctx.dry_run:
            return ok({"would_scroll": amount})
        moved = await asyncio.to_thread(controller.scroll, amount)
        return ok({"scrolled": amount}) if moved else fail("scroll failed")

    key_map = {
        "copy": ("command", "c"),
        "paste": ("command", "v"),
        "undo": ("command", "z"),
        "redo": ("command", "shift", "z"),
        "select_all": ("command", "a"),
        "hide_app": ("command", "h"),
    }

    async def key_combo(args: Mapping[str, Any], ctx: ToolContext) -> ToolResult:
        combo = str(args["combo"])
        keys = key_map[combo]
        if ctx.dry_run:
            return ok({"would_press": combo})
        pressed = await asyncio.to_thread(controller.key_combo, *keys)
        return ok({"pressed": combo}) if pressed else fail("key combination failed")

    async def lock_screen(args: Mapping[str, Any], ctx: ToolContext) -> ToolResult:
        del args
        if ctx.dry_run:
            return ok({"would_lock": True})
        locked = await asyncio.to_thread(controller.lock_screen)
        return ok({"locked": True}) if locked else fail("lock screen failed")

    def close_prompt(args: Mapping[str, Any], call_id: str) -> str:
        del args
        app = controller.frontmost_app()
        if app:
            confirmed_apps[call_id] = app
        label = app or "unknown frontmost application"
        return f"Close {label}? This will quit the currently frontmost application."

    async def close_app(args: Mapping[str, Any], ctx: ToolContext) -> ToolResult:
        del args
        confirmed_app = confirmed_apps.pop(ctx.call_id, None)
        if ctx.dry_run:
            return ok({"would_close": confirmed_app})
        current = await asyncio.to_thread(controller.frontmost_app)
        if not confirmed_app or current != confirmed_app:
            return fail("frontmost application changed; request the action again")
        closed = await asyncio.to_thread(controller.close_frontmost)
        return ok({"closed": confirmed_app}) if closed else fail("application could not be closed")

    async def delete_selected(args: Mapping[str, Any], ctx: ToolContext) -> ToolResult:
        del args
        if ctx.dry_run:
            return ok({"would_delete_selected": True})
        deleted = await asyncio.to_thread(controller.delete_selected)
        return ok({"deleted_selected_item": True}) if deleted else fail("delete action failed")

    async def type_text(args: Mapping[str, Any], ctx: ToolContext) -> ToolResult:
        text = str(args["text"])
        if any(ord(char) < 32 or ord(char) == 127 for char in text):
            return fail("control characters are not allowed")
        if ctx.dry_run:
            return ok({"would_type_length": len(text)})
        typed = await asyncio.to_thread(controller.type_text, text)
        return ok({"typed_length": len(text)}) if typed else fail("typing failed")

    path_schema = {
        "type": "string",
        "minLength": 1,
        "maxLength": 4096,
        "x-path": True,
    }
    return [
        FunctionTool(
            ToolSpec(
                "mac.open_app",
                (
                    "Open an installed macOS application or known folder. "
                    "Do not use for arbitrary shell commands."
                ),
                {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "minLength": 1, "maxLength": 200}
                    },
                    "required": ["name"],
                    "additionalProperties": False,
                },
                Tier.REVERSIBLE,
            ),
            open_app,
        ),
        FunctionTool(
            ToolSpec(
                "mac.open_url",
                (
                    "Open a valid http or https URL in the default browser. "
                    "Do not use for file or custom URL schemes."
                ),
                {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "minLength": 8, "maxLength": 2048}
                    },
                    "required": ["url"],
                    "additionalProperties": False,
                },
                Tier.REVERSIBLE,
            ),
            open_url,
        ),
        FunctionTool(
            ToolSpec(
                "mac.open_path",
                (
                    "Open a path in Finder using the macOS open command. "
                    "Do not use for protected files."
                ),
                {
                    "type": "object",
                    "properties": {"path": path_schema},
                    "required": ["path"],
                    "additionalProperties": False,
                },
                Tier.REVERSIBLE,
            ),
            open_path,
        ),
        FunctionTool(
            ToolSpec(
                "browser.search",
                (
                    "Open a web search for a user query. "
                    "Do not use to submit forms or access private networks."
                ),
                {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "minLength": 1, "maxLength": 500}
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
                Tier.REVERSIBLE,
            ),
            search,
        ),
        FunctionTool(
            ToolSpec(
                "mac.set_volume",
                "Set system output volume between 0 and 100.",
                {
                    "type": "object",
                    "properties": {
                        "value": {"type": "integer", "minimum": 0, "maximum": 100}
                    },
                    "required": ["value"],
                    "additionalProperties": False,
                },
                Tier.REVERSIBLE,
            ),
            set_volume,
        ),
        FunctionTool(
            ToolSpec(
                "mac.mute",
                "Mute system output audio. Do not use to pause or stop media.",
                _empty_schema(),
                Tier.REVERSIBLE,
            ),
            mute,
        ),
        FunctionTool(
            ToolSpec(
                "mac.screenshot",
                "Capture the main display to the Desktop.",
                _empty_schema(),
                Tier.REVERSIBLE,
            ),
            screenshot,
        ),
        FunctionTool(
            ToolSpec(
                "mac.scroll",
                "Scroll the current window by -50 to 50 units.",
                {
                    "type": "object",
                    "properties": {
                        "amount": {"type": "integer", "minimum": -50, "maximum": 50}
                    },
                    "required": ["amount"],
                    "additionalProperties": False,
                },
                Tier.REVERSIBLE,
            ),
            scroll,
        ),
        FunctionTool(
            ToolSpec(
                "mac.key_combo",
                "Press one allow-listed keyboard shortcut.",
                {
                    "type": "object",
                    "properties": {
                        "combo": {"type": "string", "enum": list(key_map)}
                    },
                    "required": ["combo"],
                    "additionalProperties": False,
                },
                Tier.REVERSIBLE,
            ),
            key_combo,
        ),
        FunctionTool(
            ToolSpec(
                "mac.lock_screen",
                "Lock the current macOS session.",
                _empty_schema(),
                Tier.REVERSIBLE,
            ),
            lock_screen,
        ),
        FunctionTool(
            ToolSpec(
                "mac.close_app",
                (
                    "Quit the currently frontmost application. "
                    "Do not use unless the user explicitly asks to close it."
                ),
                _empty_schema(),
                Tier.CONFIRM,
            ),
            close_app,
            close_prompt,
        ),
        FunctionTool(
            ToolSpec(
                "mac.delete_selected",
                (
                    "Delete the currently selected item using the legacy macOS delete shortcut. "
                    "Do not use unless the user explicitly requests deletion."
                ),
                _empty_schema(),
                Tier.CONFIRM,
            ),
            delete_selected,
        ),
        FunctionTool(
            ToolSpec(
                "mac.type_text",
                (
                    "Type up to 500 plain characters into the focused application. "
                    "Do not use for passwords or secrets."
                ),
                {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "maxLength": 500}
                    },
                    "required": ["text"],
                    "additionalProperties": False,
                },
                Tier.CONFIRM,
            ),
            type_text,
        ),
    ]
