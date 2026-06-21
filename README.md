# Underwriting Decision MCP

社内デモ用の保険引受判断支援 MCP。申込書・健康告知書・健康診断結果を読み取り、
根拠付きの判断候補を返す。最終的な引受決定は行わず、recommendation は決定論ルール
エンジンでのみ決める。

仕様の正本は [UNDERWRITING_MCP_IMPLEMENTATION_V2.md](UNDERWRITING_MCP_IMPLEMENTATION_V2.md)。
旧版は [UNDERWRITING_MCP_IMPLEMENTATION.md](UNDERWRITING_MCP_IMPLEMENTATION.md)。

## Local Demo

```bash
make install
make generate-samples
make test
make dev-mcp
```

`APP_MODE=mock` ではAWSなしで Case A/B/C fixture を処理できる。実PDFアップロードの
抽出はAWS pipeline用で、mockでは `NOT_AVAILABLE_IN_MODE` を返す。

## V2 Distribution Model

- Cowork on 3P inference: Amazon Bedrock Claude
- Remote MCP: internet-facing HTTPS endpoint, distributed by `managedMcpServers`
- Plugin: skill-only organization Plugin, no `.mcp.json`, no MCP secret
- Upload: Plugin script posts PDFs to `/v1/cases/{case_id}/documents/{document_type}`
- Auth: `AUTH_MODE=jwt` for public MCP; upload tokens are separate short-lived single-use tokens

Other-PC distribution assets live in [deploy/cowork](deploy/cowork/).
The Plugin package is produced by:

```bash
make package-plugin
```

## Data Boundary

This demo is not air-gapped. The intended boundary is that business data is not sent
to Anthropic's inference platform. Cowork runtime download traffic to `downloads.claude.ai`
is expected. See [docs/DATA_BOUNDARY.md](docs/DATA_BOUNDARY.md).

## Main Layout

- `underwriting_core/`: deterministic rules, canonical facts, result assembly, explain, what-if
- `underwriting_app/`: service layer, job/case models, ports, mock adapters, upload validation
- `underwriting_mcp/`: FastMCP server, JWT auth, Upload API
- `lambdas/underwriting_workflow/`: Textract, Bedrock normalization, final assembly worker
- `plugin/underwriting-review/`: skill-only organization Plugin
- `deploy/cowork/`: managed configuration templates and installer scripts
- `infra/`: AWS CDK v2 stacks
- `samples/`: fictional demo cases and generated PDFs
- `docs/`: architecture, deployment, data boundary, security, demo notes

## Live Smoke

After deployment and token issuance:

```bash
export MCP_URL="https://<mcp-host>/mcp"
export MCP_BEARER_TOKEN="<demo-jwt>"
RUN_AWS_LIVE_TESTS=1 make smoke-test
```

This creates a case, uploads generated PDFs, starts the AWS workflow, polls the result, and checks the expected recommendation.

## AWS Cost Modes

The default CDK deployment is a private, production-like demo shape with Interface VPC Endpoints.
For short live demos with only fictional sample forms, use `-c deploymentMode=demo-low-cost` to
avoid those endpoint-hour charges. In that mode the workflow Lambda runs outside the VPC and the
MCP Fargate task runs in public subnets behind the HTTPS ALB. Tokyo low-cost demos use deterministic
demo extraction because Amazon Textract is not available in `ap-northeast-1`. See
[docs/DEPLOY.md](docs/DEPLOY.md).

判定区分: `ELIGIBLE_CANDIDATE` / `REFER` / `NOT_ELIGIBLE_CANDIDATE`。
すべて架空のデモ用ルールであり、実在保険会社の基準ではない。
