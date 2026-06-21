"""MCP プロトコル contract テスト（§24.2）。

実 HTTP の Streamable HTTP で initialize / tools.list / tools.call / resources /
structuredContent と outputSchema の一致 / tool execution error / Origin 拒否を検証する。
"""
from __future__ import annotations

import json

import httpx
import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

EXPECTED_TOOLS = {
    "create_underwriting_case",
    "start_underwriting_review",
    "get_underwriting_review",
    "explain_underwriting_review",
    "simulate_underwriting_change",
    "list_demo_cases",
}
READ_ONLY_TOOLS = {
    "get_underwriting_review",
    "explain_underwriting_review",
    "simulate_underwriting_change",
    "list_demo_cases",
}


@pytest.mark.anyio
async def test_initialize_and_tools_list(mcp_server) -> None:
    async with streamablehttp_client(mcp_server.mcp_url) as (read, write, _):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            assert init.serverInfo.name == "Underwriting Review"

            tools = (await session.list_tools()).tools
            names = {t.name for t in tools}
            assert EXPECTED_TOOLS <= names

            by_name = {t.name: t for t in tools}
            # 参照系・What-if は readOnlyHint=True（§8.5）。
            for name in READ_ONLY_TOOLS:
                assert by_name[name].annotations is not None
                assert by_name[name].annotations.readOnlyHint is True
            # create/start は read-only にしない。
            assert by_name["create_underwriting_case"].annotations.readOnlyHint is False
            # 全 tool に outputSchema がある（§8.4）。
            for tool in tools:
                assert tool.outputSchema is not None


@pytest.mark.anyio
async def test_tools_call_full_flow_with_structured_content(mcp_server) -> None:
    async with streamablehttp_client(mcp_server.mcp_url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()

            demos = await session.call_tool("list_demo_cases", {})
            assert demos.isError is False
            assert demos.structuredContent is not None

            start = await session.call_tool(
                "start_underwriting_review",
                {"case_id": "uw_demo_case_b", "ruleset_version": "demo-medical-2026-01"},
            )
            assert start.isError is False
            job_id = start.structuredContent["job_id"]
            assert job_id.startswith("job_")

            got = await session.call_tool("get_underwriting_review", {"job_id": job_id})
            assert got.isError is False
            payload = got.structuredContent
            assert payload["completed"] is True
            assert payload["result"]["recommendation"] == "REFER"
            # structuredContent と text content が同内容（§8.4 後方互換）。
            text = json.loads(got.content[0].text)
            assert text == payload


@pytest.mark.anyio
async def test_tool_execution_error_is_structured(mcp_server) -> None:
    async with streamablehttp_client(mcp_server.mcp_url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            res = await session.call_tool(
                "get_underwriting_review", {"job_id": "job_does_not_exist"}
            )
            assert res.isError is True
            body = res.content[0].text
            assert "JOB_NOT_FOUND" in body
            assert "next_action" in body  # 次の行動を含む（§18）


@pytest.mark.anyio
async def test_resources_list_and_read(mcp_server) -> None:
    async with streamablehttp_client(mcp_server.mcp_url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            # ルールセット resource は引数なしで読める。
            templates = (await session.list_resource_templates()).resourceTemplates
            uris = {t.uriTemplate for t in templates}
            assert "underwriting://cases/{case_id}/result" in uris
            assert "underwriting://rulesets/{ruleset_version}" in uris

            content = await session.read_resource("underwriting://rulesets/demo-medical-2026-01")
            text = content.contents[0].text
            assert "DEMO-UW-017" in text


def test_origin_rejection(mcp_server) -> None:
    # 許可外 Origin はブロックされる（§8.1 / §20）。
    with httpx.Client(timeout=10) as client:
        resp = client.post(
            mcp_server.mcp_url,
            headers={
                "Origin": "https://evil.example",
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        )
    assert resp.status_code >= 400


def test_allowed_origin_passes_handshake(mcp_server) -> None:
    # 許可 Origin は少なくとも Origin 検証では拒否されない（初期化前なので 4xx でも Origin 起因でない）。
    with httpx.Client(timeout=10) as client:
        resp = client.post(
            mcp_server.mcp_url,
            headers={
                "Origin": "https://claude.ai",
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
            json={"jsonrpc": "2.0", "id": 1, "method": "ping", "params": {}},
        )
    assert "Invalid Origin" not in resp.text
