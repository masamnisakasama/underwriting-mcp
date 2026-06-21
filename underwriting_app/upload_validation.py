"""アップロード PDF の純粋検証（§7.4）。IO なし・外部ライブラリなしでテスト可能。

- PDF magic bytes（%PDF-）
- 暗号化 PDF 検出（/Encrypt）
- サイズ上限
- ページ数概算と上限（多ページ PDF 前提, §3.4 / §18 PAGE_LIMIT_EXCEEDED）
- SHA-256 計算
- ファイル名サニタイズ（S3 key に利用者入力をそのまま使わない, §7.4）
"""
from __future__ import annotations

import hashlib
import re

from .errors import ErrorCode, ToolError

MAX_BYTES = 50 * 1024 * 1024
MAX_PAGES_PER_FILE = 20
MAX_FILES_PER_CASE = 5
MAX_PAGES_PER_CASE = 30
PDF_MAGIC = b"%PDF-"

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")
_PAGE_COUNT = re.compile(rb"/Type\s*/Page[^s]")


def sanitize_filename(name: str) -> str:
    """英数字・``._-`` 以外を ``_`` にし、パス区切り・先頭ドットを除去する。"""
    base = name.replace("\\", "/").rsplit("/", 1)[-1]
    cleaned = _SAFE_NAME.sub("_", base).strip("._")
    cleaned = cleaned[:128]
    return cleaned or "document.pdf"


def count_pdf_pages(data: bytes) -> int:
    """``/Type /Page`` 出現数による概算。0 のときは最低 1 とみなす。"""
    return max(1, len(_PAGE_COUNT.findall(data)))


def validate_pdf(
    data: bytes,
    *,
    declared_size: int | None = None,
    content_type: str | None = None,
) -> tuple[str, int]:
    """PDF を検証し ``(sha256, page_count)`` を返す。不正時は :class:`ToolError`。"""
    if content_type is not None:
        normalized = content_type.split(";", 1)[0].strip().lower()
        if normalized not in {"application/pdf", "application/octet-stream"}:
            raise ToolError(
                ErrorCode.UNSUPPORTED_FILE_TYPE,
                f"PDF ではありません（Content-Type: {content_type}）。",
                "Content-Type application/pdf の PDF ファイルをアップロードしてください。",
            )
    if declared_size is not None and declared_size != len(data):
        raise ToolError(
            ErrorCode.INVALID_INPUT,
            "Content-Length と本文サイズが一致しません。",
            "アップロードを再送してください。",
        )
    if len(data) > MAX_BYTES:
        raise ToolError(
            ErrorCode.PDF_TOO_LARGE,
            f"PDF がサイズ上限（{MAX_BYTES // (1024 * 1024)}MB）を超えています。",
            "ファイルを分割または圧縮してください。",
        )
    if not data.startswith(PDF_MAGIC):
        raise ToolError(
            ErrorCode.UNSUPPORTED_FILE_TYPE,
            "PDF ではありません（magic bytes 不一致）。",
            "PDF ファイルをアップロードしてください。",
        )
    if b"/Encrypt" in data[:2_000_000]:
        raise ToolError(
            ErrorCode.PDF_ENCRYPTED,
            "暗号化された PDF は処理できません。",
            "暗号化を解除した PDF をアップロードしてください。",
        )
    pages = count_pdf_pages(data)
    if pages > MAX_PAGES_PER_FILE:
        raise ToolError(
            ErrorCode.PAGE_LIMIT_EXCEEDED,
            f"ページ数（{pages}）が1ファイル上限（{MAX_PAGES_PER_FILE}）を超えています。",
            "対象ページのみの PDF をアップロードしてください。",
        )
    sha256 = "sha256:" + hashlib.sha256(data).hexdigest()
    return sha256, pages
