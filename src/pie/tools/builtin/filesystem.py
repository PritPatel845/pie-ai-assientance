from __future__ import annotations

import heapq
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pie.safety.permissions import Tier
from pie.tools.base import FunctionTool, ToolContext, ToolResult, ToolSpec, fail, ok


_MAX_TEXT_BYTES = 100 * 1024
_MAX_DIRECTORY_ENTRIES = 200


def build_filesystem_tools() -> list[FunctionTool]:
    async def list_dir(args: Mapping[str, Any], ctx: ToolContext) -> ToolResult:
        path = Path(str(args["path"])).expanduser()
        if ctx.dry_run:
            return ok({"path": str(path), "entries": [], "dry_run": True})
        if not path.is_dir():
            return fail("path is not a directory")
        try:
            # Keep memory bounded even when a directory contains millions of entries.
            with os.scandir(path) as iterator:
                selected = heapq.nsmallest(
                    _MAX_DIRECTORY_ENTRIES + 1,
                    iterator,
                    key=lambda item: item.name.casefold(),
                )
        except OSError as exc:
            return fail(f"cannot list directory: {type(exc).__name__}")
        entries = selected[:_MAX_DIRECTORY_ENTRIES]
        return ok(
            {
                "path": str(path),
                "entries": [
                    {
                        "name": item.name,
                        "type": "directory" if item.is_dir(follow_symlinks=False) else "file",
                    }
                    for item in entries
                ],
                "truncated": len(selected) > _MAX_DIRECTORY_ENTRIES,
            }
        )

    async def read_text(args: Mapping[str, Any], ctx: ToolContext) -> ToolResult:
        path = Path(str(args["path"])).expanduser()
        if ctx.dry_run:
            return ok({"path": str(path), "dry_run": True})
        try:
            # Read one byte beyond the limit so oversized files are rejected without
            # loading their entire contents into memory.
            with path.open("rb") as handle:
                data = handle.read(_MAX_TEXT_BYTES + 1)
        except OSError as exc:
            return fail(f"cannot read file: {type(exc).__name__}")
        if len(data) > _MAX_TEXT_BYTES:
            return fail("file exceeds 100 KB limit")
        try:
            return ok(data.decode("utf-8", errors="strict"))
        except UnicodeDecodeError:
            return fail("file is not valid UTF-8 text")

    async def write_text(args: Mapping[str, Any], ctx: ToolContext) -> ToolResult:
        path = Path(str(args["path"])).expanduser()
        content = str(args["content"])
        if ctx.dry_run:
            return ok(
                {
                    "path": str(path),
                    "bytes": len(content.encode("utf-8")),
                    "dry_run": True,
                }
            )
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            flags = os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW
            flags |= os.O_TRUNC if path.exists() else os.O_EXCL
            descriptor = os.open(path, flags, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(content)
            return ok({"path": str(path), "bytes": len(content.encode("utf-8"))})
        except OSError as exc:
            return fail(f"cannot write file: {type(exc).__name__}")

    path_schema = {
        "type": "string",
        "minLength": 1,
        "maxLength": 4096,
        "x-path": True,
    }
    return [
        FunctionTool(
            ToolSpec(
                "fs.list_dir",
                "List at most 200 entries in an allowed folder. Do not use for recursive scans.",
                {
                    "type": "object",
                    "properties": {"path": path_schema},
                    "required": ["path"],
                    "additionalProperties": False,
                },
                Tier.READ,
                platforms=("darwin", "linux", "win32"),
            ),
            list_dir,
        ),
        FunctionTool(
            ToolSpec(
                "fs.read_text",
                "Read a UTF-8 text file up to 100 KB. Do not use for secrets or binary files.",
                {
                    "type": "object",
                    "properties": {"path": path_schema},
                    "required": ["path"],
                    "additionalProperties": False,
                },
                Tier.READ,
            ),
            read_text,
        ),
        FunctionTool(
            ToolSpec(
                "fs.write_text",
                (
                    "Write UTF-8 text to a file. Confirmation is required when overwriting "
                    "or writing outside the sandbox."
                ),
                {
                    "type": "object",
                    "properties": {
                        "path": {
                            **path_schema,
                            "x-confirm-if-exists": True,
                            "x-confirm-outside-sandbox": True,
                        },
                        "content": {"type": "string", "maxLength": 100000},
                    },
                    "required": ["path", "content"],
                    "additionalProperties": False,
                },
                Tier.REVERSIBLE,
                platforms=("darwin", "linux", "win32"),
            ),
            write_text,
        ),
    ]
