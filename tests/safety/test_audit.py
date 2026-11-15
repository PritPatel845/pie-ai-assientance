from __future__ import annotations

import json
import os
from pathlib import Path

from pie.safety.audit import AuditLog, redact


def test_audit_redacts_secrets_and_typed_text(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    audit = AuditLog(path)
    assert audit.write(
        {
            "tool": "mac.type_text",
            "args": {"text": "my private text", "api_token": "secret-value"},
            "ok": True,
        }
    )
    record = json.loads(path.read_text(encoding="utf-8"))
    assert record["args"]["text"] == {"length": 15}
    assert record["args"]["api_token"] == "***"


def test_audit_redacts_filesystem_write_content(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    AuditLog(path).write(
        {"tool": "fs.write_text", "args": {"path": "/tmp/a", "content": "private"}}
    )
    record = json.loads(path.read_text(encoding="utf-8"))
    assert record["args"]["content"] == {"length": 7}


def test_audit_file_permissions_are_private(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    assert AuditLog(path).write({"tool": "system.time", "args": {}})
    assert os.stat(path).st_mode & 0o777 == 0o600


def test_audit_rotates_at_configured_size(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    audit = AuditLog(path, max_bytes=100)
    for index in range(5):
        assert audit.write({"index": index, "message": "x" * 80})
    assert path.with_name("audit.jsonl.1").exists()
    assert path.exists()


def test_audit_failure_is_non_blocking(tmp_path: Path) -> None:
    parent = tmp_path / "not-a-directory"
    parent.write_text("file", encoding="utf-8")
    assert not AuditLog(parent / "audit.jsonl").write({"tool": "system.time"})


def test_redact_recurses_through_nested_data() -> None:
    safe = redact(
        {"nested": {"password": "p", "value": 4}, "api_key": "k"},
    )
    assert safe == {"nested": {"password": "***", "value": 4}, "api_key": "***"}



def test_audit_redacts_search_query_and_url_query_parameters() -> None:
    search = redact({"query": "my private medical search"}, tool="browser.search")
    url = redact(
        {"url": "https://example.com/path?access_token=secret"},
        tool="mac.open_url",
    )
    assert search == {"query": {"length": 25}}
    assert url == {"url": {"host": "example.com", "length": 44}}
