#!/usr/bin/env python3
"""V2 demo MCP JWT を発行する（§16.2）。

secret は標準出力に出さない。管理者は生成済みtokenを managedMcpServers に短期配布する。
"""
from __future__ import annotations

import argparse
import os
import sys

from underwriting_mcp.auth import issue_hs256_jwt


def _load_secret(args: argparse.Namespace) -> str | None:
    if args.secret_id:
        import boto3

        response = boto3.client("secretsmanager").get_secret_value(SecretId=args.secret_id)
        return response.get("SecretString")
    return os.environ.get(args.secret_env)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--subject", default="demo-user")
    parser.add_argument("--ttl-seconds", type=int, default=24 * 60 * 60)
    parser.add_argument("--issuer", default="underwriting-demo")
    parser.add_argument("--audience", default="underwriting-mcp")
    parser.add_argument(
        "--secret-env",
        default="MCP_JWT_SECRET",
        help="JWT signing secret を読む環境変数名",
    )
    parser.add_argument(
        "--secret-id",
        help="Secrets Manager secret id/name/ARN. 指定時は --secret-env より優先。",
    )
    args = parser.parse_args()

    secret = _load_secret(args)
    if not secret:
        print(f"{args.secret_id or args.secret_env} is required", file=sys.stderr)
        return 2
    if args.ttl_seconds <= 0 or args.ttl_seconds > 24 * 60 * 60:
        print("--ttl-seconds must be between 1 and 86400", file=sys.stderr)
        return 2

    print(
        issue_hs256_jwt(
            secret=secret,
            subject=args.subject,
            issuer=args.issuer,
            audience=args.audience,
            ttl_seconds=args.ttl_seconds,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
