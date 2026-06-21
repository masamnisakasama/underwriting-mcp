---
name: review-case
description: 複数ページの保険申込書、健康告知書、健康診断結果をAWS上のMCPへ送り、根拠付きの引受判断候補を作成する。
---

# Review Case

Use the managed MCP server named `underwriting-decision`. Do not add another MCP
definition from this Plugin.

1. Find PDF files in the attached workspace folder. Use only files inside the allowed workspace.
2. Do not decide document type from file names alone. Inspect visible content and present the candidate mapping.
3. Call `create_underwriting_case` with product `DEMO_MEDICAL_01` and expected documents.
4. For each returned upload slot, run:

```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/review-case/scripts/upload_case.py" \
  --upload-url "<upload_url>" \
  --upload-token "<upload_token>" \
  --pdf "<workspace-pdf-path>"
```

5. Confirm each upload response has `status=UPLOADED`, `sha256`, and `page_count`.
6. Call `start_underwriting_review` with ruleset `demo-medical-2026-02`.
7. Poll `get_underwriting_review` using `next_poll_after_seconds` until `completed=true`.
8. If completed, display the report in Japanese in this order:
   judgment candidate, main reasons, missing information, contradictions, applied rules,
   evidence list with document/page/quoted value, human review items, disclaimer.
9. Save the same report as `underwriting-report.md` in the workspace.
10. If failed, show stage, error code, and a concrete retry action.

Never treat this as a final insurance underwriting decision. The rules are fictional demo rules.
