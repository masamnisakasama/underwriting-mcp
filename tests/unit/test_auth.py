from __future__ import annotations

import pytest

from underwriting_mcp.auth import AuthError, issue_hs256_jwt, verify_bearer_jwt


def test_issue_and_verify_demo_jwt() -> None:
    token = issue_hs256_jwt(secret="secret", subject="user-a", now=1_800_000_000)
    subject = verify_bearer_jwt(
        f"Bearer {token}",
        secret="secret",
        issuer="underwriting-demo",
        audience="underwriting-mcp",
    )
    assert subject.subject == "user-a"
    assert subject.token_hash.startswith("sha256:")


def test_verify_rejects_wrong_audience() -> None:
    token = issue_hs256_jwt(
        secret="secret",
        subject="user-a",
        audience="other",
    )
    with pytest.raises(AuthError):
        verify_bearer_jwt(
            f"Bearer {token}",
            secret="secret",
            issuer="underwriting-demo",
            audience="underwriting-mcp",
        )
