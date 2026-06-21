# Security

- Public APIs require authentication in non-demo environments.
- `AUTH_MODE=jwt` validates `iss`, `aud`, `exp`, and signature.
- Upload tokens are short-lived and single-use.
- PDF validation checks MIME type, PDF signature, encryption marker, file size, per-file pages, and total case pages.
- Logs must not include bearer tokens, upload tokens, PDF bodies, names, medical text, or full Bedrock prompts/responses.
- The Plugin package intentionally excludes `.mcp.json` and secrets.
