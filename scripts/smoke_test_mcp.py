#!/usr/bin/env python3
"""Live MCP smoke test for deployed HTTPS endpoint.

Required env:
- MCP_URL=https://host/mcp
- MCP_BEARER_TOKEN=<managed MCP JWT>

Optional:
- SAMPLE_CASE_DIR=samples/case-a
- RULESET_VERSION=demo-medical-2026-01
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

DOCS = {
    "APPLICATION_FORM": "application_form.pdf",
    "MEDICAL_DISCLOSURE": "medical_disclosure.pdf",
    "HEALTH_CHECK": "health_check.pdf",
}


async def _call(session: ClientSession, tool: str, args: dict[str, Any]) -> dict[str, Any]:
    result = await session.call_tool(tool, args)
    if result.isError:
        raise RuntimeError(result.content[0].text)
    assert result.structuredContent is not None
    return dict(result.structuredContent)


def _upload(slot: dict[str, Any], pdf: Path) -> None:
    with httpx.Client(timeout=120) as client:
        with pdf.open("rb") as fp:
            response = client.post(
                slot["upload_url"],
                headers={"Authorization": f"Bearer {slot['upload_token']}"},
                files={"file": (pdf.name, fp, "application/pdf")},
            )
    if response.status_code >= 400:
        raise RuntimeError(f"upload failed: {response.status_code} {response.text}")
    payload = response.json()
    if payload.get("status") != "UPLOADED":
        raise RuntimeError(f"unexpected upload response: {payload}")
    print(f"uploaded {pdf.name}: {payload['sha256']} pages={payload['page_count']}")


async def main() -> int:
    mcp_url = os.environ.get("MCP_URL")
    token = os.environ.get("MCP_BEARER_TOKEN")
    if not token and os.environ.get("MCP_JWT_SECRET_ID"):
        token = subprocess.check_output(
            [
                sys.executable,
                "scripts/issue_demo_mcp_token.py",
                "--secret-id",
                os.environ["MCP_JWT_SECRET_ID"],
                "--subject",
                "live-smoke",
            ],
            text=True,
        ).strip()
    if not mcp_url or not token:
        print(
            "MCP_URL and MCP_BEARER_TOKEN are required "
            "(or set MCP_JWT_SECRET_ID to issue a token)",
            file=sys.stderr,
        )
        return 2

    sample_dir = Path(os.environ.get("SAMPLE_CASE_DIR", "samples/case-a"))
    expected = json.loads((sample_dir / "expected-result.json").read_text("utf-8"))
    case_meta = json.loads((sample_dir / "case.json").read_text("utf-8"))
    headers = {"Authorization": f"Bearer {token}"}

    async with streamablehttp_client(mcp_url, headers=headers) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            created = await _call(
                session,
                "create_underwriting_case",
                {
                    "case_name": f"live-{case_meta['case_name']}",
                    "product_code": case_meta["product_code"],
                    "applicant_age": case_meta["applicant_age"],
                    "expected_documents": list(DOCS),
                },
            )
            for slot in created["uploads"]:
                pdf = sample_dir / DOCS[slot["document_type"]]
                _upload(slot, pdf)

            started = await _call(
                session,
                "start_underwriting_review",
                {
                    "case_id": created["case_id"],
                    "ruleset_version": os.environ.get(
                        "RULESET_VERSION", "demo-medical-2026-01"
                    ),
                },
            )
            job_id = started["job_id"]
            for _ in range(80):
                got = await _call(session, "get_underwriting_review", {"job_id": job_id})
                if got.get("completed"):
                    result = got["result"]
                    print(json.dumps(result, ensure_ascii=False, indent=2))
                    if result["recommendation"] != expected["recommendation"]:
                        raise RuntimeError(
                            f"recommendation mismatch: {result['recommendation']} != "
                            f"{expected['recommendation']}"
                        )
                    return 0
                progress = got["progress"]
                print(
                    f"{progress['status']} {progress['stage']} "
                    f"{progress['progress_percent']}%"
                )
                await asyncio.sleep(progress.get("next_poll_after_seconds", 3))
            raise TimeoutError("review did not complete in time")


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
