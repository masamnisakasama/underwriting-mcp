"""Tool 実行エラー（§18）。各エラーに「次に取るべき行動」を含める。"""
from __future__ import annotations

from enum import Enum


class ErrorCode(str, Enum):
    INVALID_INPUT = "INVALID_INPUT"
    UNSUPPORTED_FILE_TYPE = "UNSUPPORTED_FILE_TYPE"
    PDF_ENCRYPTED = "PDF_ENCRYPTED"
    PDF_TOO_LARGE = "PDF_TOO_LARGE"
    PAGE_LIMIT_EXCEEDED = "PAGE_LIMIT_EXCEEDED"
    MISSING_REQUIRED_DOCUMENT = "MISSING_REQUIRED_DOCUMENT"
    UPLOAD_TOKEN_EXPIRED = "UPLOAD_TOKEN_EXPIRED"
    UPLOAD_TOKEN_ALREADY_USED = "UPLOAD_TOKEN_ALREADY_USED"
    CASE_NOT_FOUND = "CASE_NOT_FOUND"
    JOB_NOT_FOUND = "JOB_NOT_FOUND"
    JOB_ALREADY_RUNNING = "JOB_ALREADY_RUNNING"
    TEXTRACT_FAILED = "TEXTRACT_FAILED"
    BEDROCK_THROTTLED = "BEDROCK_THROTTLED"
    BEDROCK_INVALID_OUTPUT = "BEDROCK_INVALID_OUTPUT"
    RULESET_NOT_FOUND = "RULESET_NOT_FOUND"
    RULE_EVALUATION_FAILED = "RULE_EVALUATION_FAILED"
    NOT_AVAILABLE_IN_MODE = "NOT_AVAILABLE_IN_MODE"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class ToolError(Exception):
    """ビジネスエラー。内部 stack trace は返さず、修正可能な説明を返す（§8.4）。"""

    def __init__(self, code: ErrorCode, message: str, next_action: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.next_action = next_action

    def to_payload(self) -> dict[str, str]:
        return {
            "error_code": self.code.value,
            "message": self.message,
            "next_action": self.next_action,
        }
