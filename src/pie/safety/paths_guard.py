from __future__ import annotations

import os
import unicodedata
from pathlib import Path
from typing import Any

from pie.safety.permissions import Tier


class PathGuardError(ValueError):
    pass


_BLOCKED_PARTS = {
    ".ssh",
    ".aws",
    ".gnupg",
    "keychains",
}


def _normal_path(value: str) -> str:
    normalised = unicodedata.normalize("NFKC", value)
    if not normalised:
        raise PathGuardError("path must not be empty")
    if any(ord(char) < 32 or ord(char) == 127 for char in normalised):
        raise PathGuardError("control characters are not allowed in paths")
    if normalised.startswith("~") and not normalised.startswith("~/"):
        raise PathGuardError("named-user home paths are not allowed")
    parts = [part if part in {".", ".."} else part.rstrip(".") for part in normalised.split(os.sep)]
    normalised = os.sep.join(parts)
    if not normalised:
        raise PathGuardError("path must not be empty")
    expanded = os.path.expanduser(normalised)
    return os.path.realpath(os.path.abspath(expanded))


def _is_inside(path: str, root: str) -> bool:
    try:
        return os.path.commonpath((path, root)) == root
    except ValueError:
        return False


def _is_blocked(path: str, audit_path: str | None) -> bool:
    home = os.path.realpath(str(Path.home()))
    relative = os.path.relpath(path, home)
    parts = {part.casefold() for part in Path(relative).parts}
    if parts & _BLOCKED_PARTS:
        return True
    name = Path(path).name.casefold()
    if name == ".env" or name.startswith(".env."):
        return True
    home_relative = os.path.relpath(path, home).casefold()
    protected_config = os.path.join(".pie", "config.toml")
    if home_relative == protected_config or home_relative.startswith(protected_config + os.sep):
        return True
    if _is_inside(path, os.path.join(home, "Library", "Keychains")):
        return True
    if audit_path:
        protected_audit = _normal_path(audit_path)
        if (
            _is_inside(path, protected_audit)
            or path.casefold().startswith(protected_audit.casefold() + ".")
            or path.casefold() == protected_audit.casefold()
        ):
            return True
    return False


def _iter_path_values(args: dict[str, Any], schema: dict[str, Any]):
    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        return
    for key, property_schema in properties.items():
        if key not in args or not isinstance(property_schema, dict):
            continue
        if property_schema.get("x-path") is True:
            yield key, args[key]


def guard_paths(
    args: dict[str, Any],
    schema: dict[str, Any],
    *,
    allowed_folders: tuple[str, ...] | list[str],
    audit_path: str | None = None,
) -> Tier:
    """Reject sensitive paths; return CONFIRM when a path leaves allowed roots."""
    effective_tier = Tier.READ
    roots = tuple(_normal_path(root) for root in allowed_folders)
    for key, raw in _iter_path_values(args, schema):
        if not isinstance(raw, str):
            raise PathGuardError(f"{key} must be a path string")
        path = _normal_path(raw)
        if _is_blocked(path, audit_path):
            raise PathGuardError("path targets a protected location")
        if not any(_is_inside(path, root) for root in roots):
            effective_tier = max(effective_tier, Tier.CONFIRM)
    return Tier(effective_tier)


__all__ = ["PathGuardError", "guard_paths"]
