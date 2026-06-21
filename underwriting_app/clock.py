"""時刻ユーティリティ（テストで差し替え可能にするため一箇所に集約）。"""
from __future__ import annotations

from datetime import datetime, timezone


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
