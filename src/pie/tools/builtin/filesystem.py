from __future__ import annotations

import heapq
import os
import stat
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pie.safety.permissions import Tier
from pie.tools.base import FunctionTool, ToolContext, ToolResult, ToolSpec, fail, ok


_MAX_TEXT_BYTES = 100 * 1024
_MAX_DIRECTORY_ENTRIES = 200


def _open_directory(path: Path, *, create: bool = False) -> int:
    """Open a canonical directory without following symlinks in any path component."""
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
        raise OSError("safe directory operations are unavailable on this platform")
    canonical = Path(os.path.abspath(path.expanduser()))
    descriptor = os.open(os.sep, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in canonical.parts[1:]:
            try:
                next_descriptor = os.open(
                    part,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                    dir_fd=descriptor,
                )
            except FileNotFoundError:
                if not create:
                    raise
                os.mkdir(part, mode=0o700, dir_fd=descriptor)
                next_descriptor = os.open(
                    part,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                    dir_fd=descriptor,
                )
            os.close(descriptor)
            descriptor = next_descriptor
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _open_regular_file(path: Path, flags: int, mode: int = 0o600) -> int:
    parent_fd = _open_directory(path.parent)
    try:
        descriptor = os.open(
            path.name,
            flags | os.O_NOFOLLOW,
            mode,
            dir_fd=parent_fd,
        )
    finally:
        os.close(parent_fd)
    if not stat.S_ISREG(os.fstat(descriptor).st_mode):
        os.close(descriptor)
        raise OSError("target is not a regular file")
    return descriptor


def build_filesystem_tools() -> list[FunctionTool]:
    confirmed_targets: dict[str, tuple[int, int] | None] = {}

    def write_prompt(args: Mapping[str, Any], call_id: str) -> str:
        path = Path(str(args["path"])).expanduser()
        try:
            info = os.stat(path, follow_symlinks=False)
            if not stat.S_ISREG(info.st_mode):
                confirmed_targets[call_id] = (-1, -1)
                return f"Cannot safely overwrite {path}: target is not a regular file."
            confirmed_targets[call_id] = (info.st_dev, info.st_ino)
            return f"Overwrite the existing file {path}?"
        except FileNotFoundError:
            confirmed_targets[call_id] = None
            return f"Create the new file {path}?"
        except OSError as exc:
            confirmed_targets[call_id] = (-1, -1)
            return f"Cannot safely inspect {path}: {type(exc).__name__}."

    def clear_write_prompt(call_id: str) -> None:
        confirmed_targets.pop(call_id, None)

    async def list_dir(args: Mapping[str, Any], ctx: ToolContext) -> ToolResult:
        path = Path(str(args["path"])).expanduser()
        if ctx.dry_run:
            return ok({"path": str(path), "entries": [], "dry_run": True})
        descriptor = -1
        try:
            descriptor = _open_directory(path)
            # Keep memory bounded even when a directory contains millions of entries.
            with os.scandir(descriptor) as iterator:
                selected = heapq.nsmallest(
                    _MAX_DIRECTORY_ENTRIES + 1,
                    iterator,
                    key=lambda item: item.name.casefold(),
                )
                entries = [
                    {
                        "name": item.name,
                        "type": "directory" if item.is_dir(follow_symlinks=False) else "file",
                    }
                    for item in selected[:_MAX_DIRECTORY_ENTRIES]
                ]
            return ok(
                {
                    "path": str(path),
                    "entries": entries,
                    "truncated": len(selected) > _MAX_DIRECTORY_ENTRIES,
                }
            )
        except OSError as exc:
            return fail(f"cannot list directory safely: {type(exc).__name__}")
        finally:
            if descriptor >= 0:
                os.close(descriptor)

    async def read_text(args: Mapping[str, Any], ctx: ToolContext) -> ToolResult:
        path = Path(str(args["path"])).expanduser()
        if ctx.dry_run:
            return ok({"path": str(path), "dry_run": True})
        descriptor = -1
        try:
            descriptor = _open_regular_file(path, os.O_RDONLY)
            with os.fdopen(descriptor, "rb") as handle:
                descriptor = -1
                # Read one byte beyond the limit so oversized files are rejected
                # without loading their entire contents into memory.
                data = handle.read(_MAX_TEXT_BYTES + 1)
        except OSError as exc:
            return fail(f"cannot read file safely: {type(exc).__name__}")
        finally:
            if descriptor >= 0:
                os.close(descriptor)
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
        parent_fd = -1
        descriptor = -1
        try:
            parent_fd = _open_directory(path.parent, create=True)
            expected = confirmed_targets.get(ctx.call_id, ...)
            flags = os.O_WRONLY | os.O_NOFOLLOW
            if expected is ... or expected is None:
                # A file created after the confirmation prompt is never overwritten.
                descriptor = os.open(
                    path.name,
                    flags | os.O_CREAT | os.O_EXCL,
                    0o600,
                    dir_fd=parent_fd,
                )
            else:
                if expected == (-1, -1):
                    raise OSError("target could not be safely inspected before approval")
                descriptor = os.open(path.name, flags, dir_fd=parent_fd)
                info = os.fstat(descriptor)
                if (info.st_dev, info.st_ino) != expected or not stat.S_ISREG(info.st_mode):
                    raise OSError("file changed after confirmation; request the action again")
                os.ftruncate(descriptor, 0)
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                descriptor = -1
                handle.write(content)
            return ok({"path": str(path), "bytes": len(content.encode("utf-8"))})
        except OSError as exc:
            return fail(f"cannot write file safely: {type(exc).__name__}")
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            if parent_fd >= 0:
                os.close(parent_fd)

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
                platforms=("darwin", "linux"),
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
                platforms=("darwin", "linux"),
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
                platforms=("darwin", "linux"),
            ),
            write_text,
            write_prompt,
            clear_write_prompt,
        ),
    ]
