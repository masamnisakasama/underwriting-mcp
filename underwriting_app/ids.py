"""ID・トークン・冪等キー生成。

case_id/job_id は時刻順ソート可能な単調プレフィックス + ランダム接尾で衝突を避ける。
冪等キーは (case_id, ruleset_version, document_hashes) から決定論的に算出する（§8.2）。
"""
from __future__ import annotations

import hashlib
import secrets
import time
from typing import Mapping

# Crockford Base32（紛らわしい I,L,O,U を除外）。
_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def _b32(n: int, width: int) -> str:
    chars = []
    for _ in range(width):
        n, rem = divmod(n, 32)
        chars.append(_ALPHABET[rem])
    return "".join(reversed(chars))


def _ulid_like() -> str:
    ts_ms = int(time.time() * 1000)
    rand = secrets.randbits(80)
    return _b32(ts_ms, 10) + _b32(rand, 16)


def new_case_id() -> str:
    return "uw_" + _ulid_like()


def new_job_id() -> str:
    return "job_" + _ulid_like()


def new_upload_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return "sha256:" + hashlib.sha256(token.encode("utf-8")).hexdigest()


def idempotency_key(
    case_id: str, ruleset_version: str, document_hashes: Mapping[str, str]
) -> str:
    """同一入力に対し同じ job を返すための決定論キー。"""
    payload = "|".join(
        [
            case_id,
            ruleset_version,
            *(f"{name}={document_hashes[name]}" for name in sorted(document_hashes)),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
