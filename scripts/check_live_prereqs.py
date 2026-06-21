#!/usr/bin/env python3
"""Check prerequisites before deploy/live smoke."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _ok(message: str) -> None:
    print(f"OK: {message}")


def _fail(errors: list[str], message: str) -> None:
    print(f"NG: {message}")
    errors.append(message)


def main() -> int:
    errors: list[str] = []
    try:
        result = subprocess.run(
            ["aws", "sts", "get-caller-identity"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
        )
    except FileNotFoundError:
        _fail(errors, "aws CLI is not installed or not on PATH")
    else:
        if result.returncode == 0:
            _ok("AWS caller identity is available")
        else:
            _fail(
                errors,
                "AWS credentials are not usable. Run aws sso login for the active profile.",
            )
            if result.stderr.strip():
                print(result.stderr.strip())

    mcp_url = os.environ.get("MCP_URL")
    if mcp_url:
        _ok("MCP_URL is set")
        if mcp_url.startswith("https://"):
            _ok("MCP_URL uses HTTPS")
        else:
            _fail(errors, "MCP_URL must start with https:// for V2 Remote MCP")
    else:
        _fail(errors, "MCP_URL is not set")

    if os.environ.get("MCP_BEARER_TOKEN"):
        _ok("MCP_BEARER_TOKEN is set")
    elif os.environ.get("MCP_JWT_SECRET_ID"):
        _ok("MCP_JWT_SECRET_ID is set; token can be issued with scripts/issue_demo_mcp_token.py")
    else:
        _fail(errors, "MCP_BEARER_TOKEN is not set")

    sample_dir = ROOT / os.environ.get("SAMPLE_CASE_DIR", "samples/case-a")
    for filename in [
        "application_form.pdf",
        "medical_disclosure.pdf",
        "health_check.pdf",
        "expected-result.json",
    ]:
        path = sample_dir / filename
        if path.is_file():
            _ok(f"sample artifact exists: {path.relative_to(ROOT)}")
        else:
            _fail(errors, f"missing sample artifact: {path.relative_to(ROOT)}")

    plugin_zip = ROOT / "dist" / "underwriting-review-plugin.zip"
    if plugin_zip.is_file():
        _ok("plugin package exists")
    else:
        _fail(errors, "plugin package is missing; run make package-plugin")

    if errors:
        print("\nLive prerequisites are incomplete.", file=sys.stderr)
        return 1
    print("\nLive prerequisites look ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
