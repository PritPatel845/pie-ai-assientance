from __future__ import annotations

from pathlib import Path

from pie.brain.quota import QuotaTracker


def test_quota_persists_and_expires(tmp_path: Path) -> None:
    now = [100.0]
    path = tmp_path / "quota.json"
    tracker = QuotaTracker(path, default_cooldown_s=20, clock=lambda: now[0])
    tracker.mark_exhausted("openai", reset_at=110.0)
    assert not tracker.is_available("openai")
    restored = QuotaTracker(path, clock=lambda: now[0])
    assert not restored.is_available("openai")
    now[0] = 111.0
    assert restored.is_available("openai")


def test_corrupt_quota_is_preserved_and_recovered(tmp_path: Path) -> None:
    path = tmp_path / "quota.json"
    path.write_text("{broken", encoding="utf-8")
    tracker = QuotaTracker(path, clock=lambda: 123.0)
    assert tracker.snapshot() == {}
    assert (tmp_path / "quota.json.corrupt-123").exists()


def test_reset_all_and_single_provider(tmp_path: Path) -> None:
    tracker = QuotaTracker(tmp_path / "quota.json")
    tracker.mark_exhausted("openai")
    tracker.mark_exhausted("anthropic")
    tracker.reset("openai")
    assert "openai" not in tracker.snapshot()
    tracker.reset()
    assert tracker.snapshot() == {}
