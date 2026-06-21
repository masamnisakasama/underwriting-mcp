#!/usr/bin/env python3
"""Cowork 3P managed configuration renderer（V2 §14.4）。"""
from __future__ import annotations

import argparse
import json
import plistlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TEMPLATES = ROOT / "templates"
GENERATED = ROOT / "generated"


def _replace(text: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        text = text.replace(key, value)
    return text


def _reg_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--aws-account-id", required=True)
    parser.add_argument("--bedrock-region", required=True)
    parser.add_argument("--sso-start-url", required=True)
    parser.add_argument("--sso-region", required=True)
    parser.add_argument("--permission-set-name", required=True)
    parser.add_argument("--bedrock-inference-profile-id", required=True)
    parser.add_argument("--mcp-host", required=True)
    parser.add_argument("--demo-mcp-token", required=True)
    parser.add_argument("--organization-uuid", required=True)
    args = parser.parse_args()

    values = {
        "REPLACE_AWS_ACCOUNT_ID": args.aws_account_id,
        "REPLACE_BEDROCK_REGION": args.bedrock_region,
        "REPLACE_AWS_SSO_START_URL": args.sso_start_url,
        "REPLACE_AWS_SSO_REGION": args.sso_region,
        "REPLACE_PERMISSION_SET_NAME": args.permission_set_name,
        "REPLACE_BEDROCK_INFERENCE_PROFILE_ID": args.bedrock_inference_profile_id,
        "REPLACE_MCP_HOST": args.mcp_host,
        "REPLACE_DEMO_MCP_TOKEN": args.demo_mcp_token,
        "REPLACE_DEPLOYMENT_ORGANIZATION_UUID": args.organization_uuid,
    }
    managed_text = _replace(
        (TEMPLATES / "managed-mcp-servers.json.template").read_text("utf-8"), values
    )
    managed = json.loads(managed_text)
    values["REPLACE_MANAGED_MCP_SERVERS_JSON"] = json.dumps(managed, separators=(",", ":"))

    config_text = _replace(
        (TEMPLATES / "cowork-3p-demo.json.template").read_text("utf-8"), values
    )
    config = json.loads(config_text)
    GENERATED.mkdir(parents=True, exist_ok=True)
    (GENERATED / "cowork-3p-demo.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    reg_lines = [
        "Windows Registry Editor Version 5.00",
        "",
        r"[HKEY_LOCAL_MACHINE\Software\Policies\Anthropic\Claude]",
    ]
    for key, value in config.items():
        encoded = json.dumps(value, separators=(",", ":")) if isinstance(value, (list, dict)) else value
        if not isinstance(encoded, str):
            encoded = json.dumps(encoded)
        reg_lines.append(f'"{key}"="{_reg_escape(encoded)}"')
    (GENERATED / "cowork-3p-demo.reg").write_text("\n".join(reg_lines) + "\n", "utf-8")

    plist = {
        "PayloadContent": [
            {
                "PayloadType": "com.anthropic.claude",
                "PayloadVersion": 1,
                "PayloadIdentifier": f"{args.organization_uuid}.claude.cowork3p",
                "PayloadUUID": args.organization_uuid,
                "PayloadDisplayName": "Claude Cowork 3P Underwriting Demo",
                **config,
            }
        ],
        "PayloadType": "Configuration",
        "PayloadVersion": 1,
        "PayloadIdentifier": f"{args.organization_uuid}.claude",
        "PayloadUUID": args.organization_uuid,
        "PayloadDisplayName": "Claude Cowork 3P Underwriting Demo",
    }
    with (GENERATED / "cowork-3p-demo.mobileconfig").open("wb") as fp:
        plistlib.dump(plist, fp)

    print(f"Wrote {GENERATED}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
