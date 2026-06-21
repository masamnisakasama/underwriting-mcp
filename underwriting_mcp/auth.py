"""MCP/API bearer JWT 認証（V2 §16.2）。

デモ用の HS256 JWT を標準ライブラリだけで検証する。token 原文は保存・ログ出力しない。
本番化時は OAuth/Cognito/社内 IdP または headersHelper に置き換える想定。
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Any


class AuthError(Exception):
    """認証失敗。外部へは汎用メッセージだけを返す。"""


@dataclass(frozen=True)
class AuthSubject:
    subject: str
    token_hash: str


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _json_decode(value: str) -> dict[str, Any]:
    try:
        decoded = json.loads(_b64url_decode(value))
    except Exception as exc:  # noqa: BLE001 - malformed auth should collapse to AuthError.
        raise AuthError("invalid token") from exc
    if not isinstance(decoded, dict):
        raise AuthError("invalid token")
    return decoded


def issue_hs256_jwt(
    *,
    secret: str,
    subject: str,
    issuer: str = "underwriting-demo",
    audience: str = "underwriting-mcp",
    ttl_seconds: int = 24 * 60 * 60,
    now: int | None = None,
) -> str:
    now = int(time.time() if now is None else now)
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "iss": issuer,
        "aud": audience,
        "sub": subject,
        "iat": now,
        "exp": now + ttl_seconds,
    }
    h = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    p = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{h}.{p}".encode("ascii")
    sig = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{h}.{p}.{_b64url_encode(sig)}"


def verify_bearer_jwt(
    authorization: str | None,
    *,
    secret: str,
    issuer: str,
    audience: str,
    clock_skew_seconds: int = 60,
) -> AuthSubject:
    if not authorization or not authorization.startswith("Bearer "):
        raise AuthError("missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    parts = token.split(".")
    if len(parts) != 3:
        raise AuthError("invalid token")

    header = _json_decode(parts[0])
    if header.get("alg") != "HS256":
        raise AuthError("unsupported token algorithm")

    signing_input = f"{parts[0]}.{parts[1]}".encode("ascii")
    expected = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    actual = _b64url_decode(parts[2])
    if not hmac.compare_digest(expected, actual):
        raise AuthError("invalid signature")

    payload = _json_decode(parts[1])
    now = int(time.time())
    if payload.get("iss") != issuer or payload.get("aud") != audience:
        raise AuthError("invalid token claims")
    exp = payload.get("exp")
    if not isinstance(exp, int) or now > exp + clock_skew_seconds:
        raise AuthError("expired token")
    nbf = payload.get("nbf")
    if isinstance(nbf, int) and now + clock_skew_seconds < nbf:
        raise AuthError("token not yet valid")
    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub:
        raise AuthError("missing subject")

    token_hash = "sha256:" + hashlib.sha256(token.encode("utf-8")).hexdigest()
    return AuthSubject(subject=sub, token_hash=token_hash)
