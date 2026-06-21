#!/usr/bin/env python3
"""Underwriting MCP Upload API へPDFを送るSkill補助script。

stdout は成功JSONだけを返し、tokenやPDF本文は出力しない。
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import secrets
import sys
import urllib.error
import urllib.request
from pathlib import Path


def _multipart_body(path: Path, field_name: str = "file") -> tuple[bytes, str]:
    boundary = "----uwmcp-" + secrets.token_hex(16)
    content_type = mimetypes.guess_type(path.name)[0] or "application/pdf"
    head = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field_name}"; filename="{path.name}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n"
    ).encode("utf-8")
    tail = f"\r\n--{boundary}--\r\n".encode("utf-8")
    return head + path.read_bytes() + tail, f"multipart/form-data; boundary={boundary}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--upload-url", required=True)
    parser.add_argument("--upload-token", required=True)
    parser.add_argument("--pdf", required=True)
    args = parser.parse_args()

    pdf = Path(args.pdf).expanduser().resolve()
    if not pdf.is_file():
        print(json.dumps({"ok": False, "error": "PDF file not found"}), file=sys.stderr)
        return 2

    body, content_type = _multipart_body(pdf)
    request = urllib.request.Request(
        args.upload_url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {args.upload_token}",
            "Content-Type": content_type,
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            payload = json.loads(exc.read().decode("utf-8"))
        except Exception:  # noqa: BLE001
            payload = {"error_code": "UPLOAD_FAILED", "message": "Upload failed"}
        print(json.dumps(payload, ensure_ascii=False), file=sys.stderr)
        return 1

    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
