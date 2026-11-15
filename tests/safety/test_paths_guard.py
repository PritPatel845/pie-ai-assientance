from __future__ import annotations

import pytest
from pathlib import Path

from pie.safety.paths_guard import PathGuardError, guard_paths
from pie.safety.permissions import Tier


SCHEMA = {
    "type": "object",
    "properties": {"path": {"type": "string", "x-path": True}},
    "required": ["path"],
    "additionalProperties": False,
}


def _guard(path: str, home: Path, allowed: Path, audit: Path) -> Tier:
    return guard_paths(
        {"path": path},
        SCHEMA,
        allowed_folders=(str(allowed),),
        audit_path=str(audit),
    )


@pytest.mark.parametrize(
    "relative",
    [
        ".ssh/id_rsa",
        ".ssh/config",
        ".aws/credentials",
        ".aws/config",
        ".gnupg/private-keys-v1.d/key",
        "Library/Keychains/login.keychain-db",
        ".pie/config.toml",
        ".pie/config.toml/child",
        "Project/.env",
        "Project/.env.local",
        "Project/.env.production",
        "Project/.ENV",
        "Project/.env.backup",
        ".ssh",
        ".aws",
        ".gnupg",
        "Library/Keychains",
        "Library/Keychains/metadata",
        ".ssh./id_rsa",
        ".aws./credentials",
        ".gnupg./private-key",
        "Project/.env.",
        "Project/.env.local.",
        "Library/KEYCHAINS/login.keychain-db",
        ".pie/config.toml.",
    ],
)
def test_protected_home_paths_are_rejected(
    relative: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    allowed = home / "allowed"
    allowed.mkdir()
    audit = home / ".pie" / "logs" / "audit.jsonl"
    with pytest.raises(PathGuardError):
        _guard(str(home / relative), home, allowed, audit)


def test_audit_file_is_protected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    allowed = home / "allowed"
    allowed.mkdir()
    audit = home / ".pie" / "logs" / "audit.jsonl"
    audit.parent.mkdir(parents=True)
    audit.touch()
    with pytest.raises(PathGuardError):
        _guard(str(audit), home, allowed, audit)


def test_audit_rotation_files_are_protected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    allowed = home / "allowed"
    allowed.mkdir()
    audit = home / ".pie" / "logs" / "audit.jsonl"
    with pytest.raises(PathGuardError):
        _guard(str(audit) + ".1", home, allowed, audit)


def test_symlink_to_protected_directory_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    allowed = home / "allowed"
    allowed.mkdir()
    (home / ".ssh").mkdir()
    link = allowed / "linked"
    link.symlink_to(home / ".ssh", target_is_directory=True)
    with pytest.raises(PathGuardError):
        _guard(str(link / "id_rsa"), home, allowed, home / ".pie/audit.jsonl")


def test_path_traversal_outside_allowed_root_requires_confirmation(
    tmp_path: Path,
) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    outside = tmp_path / "outside.txt"
    assert guard_paths(
        {"path": str(allowed / ".." / outside.name)},
        SCHEMA,
        allowed_folders=(str(allowed),),
    ) is Tier.CONFIRM


def test_path_inside_allowed_root_is_read_tier(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    assert guard_paths(
        {"path": str(allowed / "notes.txt")},
        SCHEMA,
        allowed_folders=(str(allowed),),
    ) is Tier.READ


def test_named_user_home_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(PathGuardError):
        guard_paths(
            {"path": "~another-user/.ssh/id_rsa"},
            SCHEMA,
            allowed_folders=(str(tmp_path),),
        )


def test_non_string_path_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(PathGuardError):
        guard_paths(
            {"path": 123},  # type: ignore[dict-item]
            SCHEMA,
            allowed_folders=(str(tmp_path),),
        )


def test_unmarked_path_property_is_ignored(tmp_path: Path) -> None:
    schema = {
        "type": "object",
        "properties": {"value": {"type": "string"}},
        "additionalProperties": False,
    }
    assert guard_paths(
        {"value": str(tmp_path / ".ssh" / "id_rsa")},
        schema,
        allowed_folders=(str(tmp_path),),
    ) is Tier.READ
