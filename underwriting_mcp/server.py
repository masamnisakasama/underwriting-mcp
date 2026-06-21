"""FastMCP サーバ組み立て（§8）。

6 つの tool と 3 つの resource を登録する。tool は平坦な入力スキーマ（仕様の例に一致）
を公開し、内部で service の入力モデルへ詰め替える。判定・確率的処理はここに置かない。
ビジネスエラーは ToolError -> FastMCP の ToolError(JSON) に変換し、stack trace を返さない。
"""
from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError as FastMCPToolError
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from underwriting_app.errors import ToolError
from underwriting_app.factory import build_aws_service, build_mock_service
from underwriting_app.models import (
    CreateCaseInput,
    CreateCaseOutput,
    DemoCaseSummary,
    ExplainInput,
    ExplainOutput,
    GetReviewInput,
    ReviewProgress,
    ScenarioChange,
    SimulateInput,
    SimulateOutput,
    StartReviewInput,
    StartReviewOutput,
)
from underwriting_app.service import UnderwritingService
from underwriting_core.enums import DocumentType
from underwriting_core.result import UnderwritingResult

from .config import ServerConfig
from .tool_models import GetReviewResponse
from .auth import AuthError, verify_bearer_jwt
from .upload_api import build_upload_endpoint

INSTRUCTIONS = (
    "保険引受の判断支援 MCP。OCR/抽出済み帳票から根拠付きの判断候補を返す。"
    "最終判定は行わず、recommendation は決定論ルールエンジンが決める。"
    "外部システムへの書き込みは行わない。"
)


def _guard(fn: Any) -> Any:
    """ToolError を FastMCP のエラーへ変換（structured payload, stack trace なし）。"""
    try:
        return fn()
    except ToolError as exc:
        raise FastMCPToolError(json.dumps(exc.to_payload(), ensure_ascii=False)) from None


def register_tools(mcp: FastMCP, service: UnderwritingService) -> None:
    @mcp.tool(
        name="create_underwriting_case",
        title="査定ケース作成",
        description="ケースとアップロードセッションを作成する。外部書き込みはしない。",
        structured_output=True,
        annotations=ToolAnnotations(title="査定ケース作成", readOnlyHint=False),
    )
    def create_underwriting_case(
        case_name: str,
        product_code: str,
        applicant_age: int,
        expected_documents: list[DocumentType],
        demo_fixture: str | None = None,
    ) -> CreateCaseOutput:
        return _guard(
            lambda: service.create_underwriting_case(
                CreateCaseInput(
                    case_name=case_name,
                    product_code=product_code,
                    applicant_age=applicant_age,
                    expected_documents=expected_documents,
                    demo_fixture=demo_fixture,
                )
            )
        )

    @mcp.tool(
        name="start_underwriting_review",
        title="査定開始",
        description="アップロード済み帳票の査定ワークフローを開始する（冪等）。",
        structured_output=True,
        annotations=ToolAnnotations(title="査定開始", readOnlyHint=False),
    )
    def start_underwriting_review(
        case_id: str, ruleset_version: str
    ) -> StartReviewOutput:
        return _guard(
            lambda: service.start_underwriting_review(
                StartReviewInput(case_id=case_id, ruleset_version=ruleset_version)
            )
        )

    @mcp.tool(
        name="get_underwriting_review",
        title="査定結果取得",
        description="進行状況または最終結果を取得する。",
        structured_output=True,
        annotations=ToolAnnotations(title="査定結果取得", readOnlyHint=True),
    )
    def get_underwriting_review(job_id: str) -> GetReviewResponse:
        outcome = _guard(
            lambda: service.get_underwriting_review(GetReviewInput(job_id=job_id))
        )
        if isinstance(outcome, UnderwritingResult):
            return GetReviewResponse(completed=True, result=outcome)
        assert isinstance(outcome, ReviewProgress)
        return GetReviewResponse(completed=False, progress=outcome)

    @mcp.tool(
        name="explain_underwriting_review",
        title="結果の説明",
        description="保存済み事実・ルール・根拠だけで結果への質問に答える。",
        structured_output=True,
        annotations=ToolAnnotations(title="結果の説明", readOnlyHint=True),
    )
    def explain_underwriting_review(job_id: str, question: str) -> ExplainOutput:
        return _guard(
            lambda: service.explain_underwriting_review(
                ExplainInput(job_id=job_id, question=question)
            )
        )

    @mcp.tool(
        name="simulate_underwriting_change",
        title="What-if 比較",
        description="変更を当ててルールを再評価し before/after を返す。元の結果は変えない。",
        structured_output=True,
        annotations=ToolAnnotations(title="What-if 比較", readOnlyHint=True),
    )
    def simulate_underwriting_change(
        job_id: str, changes: list[ScenarioChange]
    ) -> SimulateOutput:
        return _guard(
            lambda: service.simulate_underwriting_change(
                SimulateInput(job_id=job_id, changes=changes)
            )
        )

    @mcp.tool(
        name="list_demo_cases",
        title="デモケース一覧",
        description="事前配置されたデモケース一覧を返す（demo 環境のみ）。",
        structured_output=True,
        annotations=ToolAnnotations(title="デモケース一覧", readOnlyHint=True),
    )
    def list_demo_cases() -> list[DemoCaseSummary]:
        return _guard(service.list_demo_cases)


def register_resources(mcp: FastMCP, service: UnderwritingService) -> None:
    @mcp.resource(
        "underwriting://cases/{case_id}/result",
        name="underwriting-case-result",
        description="ケースの最新査定結果（JSON）。",
        mime_type="application/json",
    )
    def case_result(case_id: str) -> str:
        result = _guard(lambda: service.result_for_case(case_id))
        return result.model_dump_json(indent=2)

    @mcp.resource(
        "underwriting://cases/{case_id}/evidence",
        name="underwriting-case-evidence",
        description="ケースの根拠（ページ追跡可能な evidence メタ。原文 PDF は含めない）。",
        mime_type="application/json",
    )
    def case_evidence(case_id: str) -> str:
        evidence = _guard(lambda: service.evidence_for_case(case_id))
        return json.dumps(evidence, ensure_ascii=False, indent=2)

    @mcp.resource(
        "underwriting://rulesets/{ruleset_version}",
        name="underwriting-ruleset",
        description="ルールセット定義（架空のデモ用）。",
        mime_type="application/json",
    )
    def ruleset(ruleset_version: str) -> str:
        definition = _guard(lambda: service.ruleset_definition(ruleset_version))
        return json.dumps(definition, ensure_ascii=False, indent=2)


def build_service(config: ServerConfig) -> UnderwritingService:
    if config.app_mode == "mock":
        return build_mock_service(
            rulesets_dir=config.rulesets_dir,
            samples_dir=config.samples_dir,
            public_base_url=config.public_base_url,
            code_version=config.code_version,
        )
    return build_aws_service(
        rulesets_dir=config.rulesets_dir,
        public_base_url=config.public_base_url,
    )


def create_mcp(config: ServerConfig, service: UnderwritingService | None = None) -> FastMCP:
    service = service or build_service(config)
    transport_security = TransportSecuritySettings(
        enable_dns_rebinding_protection=config.enable_origin_check,
        allowed_origins=config.allowed_origins,
        allowed_hosts=config.allowed_hosts,
    )
    mcp = FastMCP(
        "Underwriting Review",
        instructions=INSTRUCTIONS,
        host=config.host,
        port=config.port,
        json_response=config.json_response,
        stateless_http=config.stateless_http,
        transport_security=transport_security,
    )
    register_tools(mcp, service)
    register_resources(mcp, service)
    return mcp


def _add_http_edges(app: Any, config: ServerConfig, service: UnderwritingService) -> Any:
    async def healthz(_: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "app_mode": config.app_mode})

    async def auth_middleware(request: Request, call_next: Any) -> Any:
        if config.auth_mode == "jwt" and request.url.path.startswith("/mcp"):
            try:
                assert config.jwt_secret is not None
                verify_bearer_jwt(
                    request.headers.get("authorization"),
                    secret=config.jwt_secret,
                    issuer=config.jwt_issuer,
                    audience=config.jwt_audience,
                )
            except AuthError:
                return JSONResponse(
                    {
                        "error_code": "UNAUTHORIZED",
                        "message": "MCP bearer token が無効です。",
                        "next_action": "管理設定の managedMcpServers token を確認してください。",
                    },
                    status_code=401,
                )
        return await call_next(request)

    app.add_middleware(BaseHTTPMiddleware, dispatch=auth_middleware)
    app.routes.append(Route("/healthz", healthz, methods=["GET"]))
    app.routes.append(
        Route(
            "/v1/cases/{case_id}/documents/{document_type}",
            build_upload_endpoint(service),
            methods=["POST"],
        )
    )
    return app


def create_app(
    config: ServerConfig | None = None,
    service: UnderwritingService | None = None,
) -> Any:
    """Streamable HTTP の ASGI アプリ（/mcp）を返す。"""
    config = (config or ServerConfig()).validate()
    service = service or build_service(config)
    app = create_mcp(config, service).streamable_http_app()
    return _add_http_edges(app, config, service)
