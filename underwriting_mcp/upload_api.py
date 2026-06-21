"""Upload API（V2 §7.2）。

Remote MCP は利用者PCのローカルPDFを直接読めないため、Skill同梱scriptからこのAPIへ
multipart uploadする。Authorization は MCP JWT ではなく case/document 単位の短期
upload token。
"""
from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse

from underwriting_app.errors import ToolError
from underwriting_app.service import UnderwritingService
from underwriting_core.enums import DocumentType


def _error_response(exc: ToolError, status_code: int = 400) -> JSONResponse:
    return JSONResponse(exc.to_payload(), status_code=status_code)


def _authorization_bearer(headers: Any) -> str | None:
    value = headers.get("authorization") or headers.get("Authorization")
    if not value or not value.startswith("Bearer "):
        return None
    return value.removeprefix("Bearer ").strip()


def build_upload_endpoint(service: UnderwritingService) -> Callable[[Request], Any]:
    async def upload_document(request: Request) -> JSONResponse:
        case_id = request.path_params["case_id"]
        try:
            document_type = DocumentType(request.path_params["document_type"])
        except ValueError:
            return JSONResponse(
                {
                    "error_code": "INVALID_INPUT",
                    "message": "未知の document_type です。",
                    "next_action": "APPLICATION_FORM / MEDICAL_DISCLOSURE / HEALTH_CHECK を指定してください。",
                },
                status_code=400,
            )

        token = _authorization_bearer(request.headers)
        if token is None:
            return JSONResponse(
                {
                    "error_code": "INVALID_INPUT",
                    "message": "upload token がありません。",
                    "next_action": "Authorization: Bearer <upload-token> を指定してください。",
                },
                status_code=401,
            )

        try:
            form = await request.form()
            upload = form.get("file")
            if upload is None or not hasattr(upload, "read"):
                return JSONResponse(
                    {
                        "error_code": "INVALID_INPUT",
                        "message": "multipart field 'file' がありません。",
                        "next_action": "PDFを multipart/form-data の file field で送信してください。",
                    },
                    status_code=400,
                )
            data = await upload.read()
            result = service.upload_document(
                case_id=case_id,
                document_type=document_type,
                upload_token=token,
                filename=getattr(upload, "filename", None) or "document.pdf",
                data=data,
                content_type=getattr(upload, "content_type", None),
            )
        except ToolError as exc:
            return _error_response(exc)

        body = json.loads(result.model_dump_json())
        return JSONResponse(body, status_code=201)

    return upload_document
