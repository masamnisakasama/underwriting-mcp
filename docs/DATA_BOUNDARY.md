# Data Boundary

This demo is not air-gapped and is not completely offline.

Business data boundary:

- Conversation and orchestration prompts use Amazon Bedrock Claude.
- PDFs are uploaded to the AWS-hosted Underwriting MCP endpoint over HTTPS.
- Document processing stays in AWS services such as S3, Textract, Step Functions, Lambda, and Bedrock.
- The backend does not call the Anthropic API.
- Claude Desktop may contact `downloads.claude.ai` to obtain the Cowork runtime bundle.
- Anthropic telemetry, nonessential services, auto-update, WebSearch, and WebFetch are disabled in the managed configuration templates.

Allowed data path:

```text
User PC -> Bedrock Runtime
User PC -> HTTPS ALB/WAF -> ECS MCP Gateway -> S3/Textract/Step Functions/Bedrock
AWS MCP -> User PC
```

Disallowed data path:

```text
Backend -> Anthropic API
Backend -> external SaaS / CRM / policy administration system
```

Use the egress list exported by Claude Desktop's third-party inference configuration as the authoritative host allowlist.
