# 実装ステータス（V2）

最終更新: 2026-06-21。作業範囲は `/Users/ikedamasahiro/Agentmemory_MVP/underwriting-mcp`
配下のみ。

## 完了

- 決定論ルールエンジン、canonical facts、result schema、What-if、根拠付き説明
- 6 MCP tools と 3 MCP resources
- Streamable HTTP MCP `/mcp`、Origin検証、ローカル `make dev-mcp`
- V2向け JWT auth (`AUTH_MODE=jwt`) と短期single-use upload token
- Upload API `/v1/cases/{case_id}/documents/{document_type}`
- PDF signature/MIME/encryption/size/page validation
- Case A/B/C fixture と再生成可能な複数ページPDF
- Skill-only organization Plugin (`plugin/underwriting-review`)
- `managedMcpServers` 正本のCowork 3P配布テンプレート、`.reg`/`.mobileconfig`レンダラ
- macOS/Windows向けPluginコピー・管理設定適用スクリプト
- Prompts、docs、ASL workflow skeleton
- AWS service adapters: S3 object store, DynamoDB job store, Step Functions start client
- Workflow Lambda: private subnet execution, Textract async document analysis, Bedrock normalization, deterministic fallback, final result assembly, failed-job marking
- Bedrock structured output repair once, plus Bedrock-generated Japanese narrative that cannot change deterministic recommendation
- AWS CDK v2: VPC endpoints, S3/KMS, DynamoDB, Docker Lambda workflow in private isolated subnets, Step Functions Map, ECS Fargate MCP in private isolated subnets, ALB, WAF
- Low-cost demo CDK mode: no Interface VPC Endpoints, workflow Lambda outside VPC, ECS Fargate task in public subnets behind ALB, WAF optional
- Low-cost Tokyo live demo uses deterministic demo extraction because Textract is not available in `ap-northeast-1`; private mode keeps Textract integration
- Textract service principal is granted read/decrypt for SSE-KMS input PDFs
- Optional ACM HTTPS listener and Route 53 alias record via CDK context
- Dockerfile for MCP server
- Live MCP smoke script, prerequisite checker, and data-boundary packaging verifier
- V2 decision categories: `REFER_INFO_REQUEST`, `REFER_MEDICAL_REVIEW`, `REFER_SENIOR_REVIEW`, `DECLINE_CANDIDATE`
- Ruleset `demo-medical-2026-02` with guardrail/screening rule metadata and v2 YAML shape
- Scenario override fixed-path validation with fail-fast invalid path errors
- V2 What-if diff output: recommendation changed, added/removed rule hits, added missing information
- Skill `review-case` now starts assessments with `demo-medical-2026-02`
- Evidence-backed prioritization and regression plan docs:
  - `docs/UNDERWRITING_AGENT_EVIDENCE_PRIORITIES.md`
  - `docs/UNDERWRITING_AGENT_TEST_PLAN.md`
- External design handoff for kintone-like self-serve MCP/MCPB:
  - `docs/SELF_SERVE_MCPB_IMPLEMENTATION_HANDOFF.md`
- Deterministic v2 `agent_findings` for ambiguous free text, scoped to `demo-medical-2026-02`
- Case D fixture for ambiguous disclosure free text
- What-if diff output includes added agent finding IDs

## 検証済み

- `make generate-samples`
- `make test`: 77 passed
- `make lint`
- `make typecheck`
- `make package-plugin`
- `make verify-data-boundary`
- `make check-live-prereqs`: fails as expected until AWS SSO and MCP env are available
- `npm run build`
- `make synth`: success with CDK warnings only using `allowHttpForLocalSynth=true`
- `npm run synth -- -c certificateArn=... -c mcpHostName=... -c bedrockModelId=...`: success and emits HTTPS/443 listener
- Synthesized workflow template includes Lambda `VpcConfig` for private subnet execution
- AWS live low-cost deploy to `https://<MCP_HOST>/mcp`
- `RUN_AWS_LIVE_TESTS=1 RULESET_VERSION=demo-medical-2026-02 make smoke-test`: success against deployed HTTPS MCP
- Live deployed scenario comparison: Case A base `ELIGIBLE_CANDIDATE` -> high blood pressure/treatment/medication What-if `REFER_MEDICAL_REVIEW`
- Live deployed agent-finding comparison: Case A base `ELIGIBLE_CANDIDATE` -> ambiguous disclosure free-text What-if `REFER_INFO_REQUEST` with `AGENT-FREE-TEXT-001`

## 残作業

- Production-grade OAuth/Cognito/headersHelper token issuer
- ACM証明書・Route53・Secrets Manager・model profileなど環境別パラメータの投入
- Bedrock-backed agent assessment Lambda, replacing the deterministic local detector when AWS mode requires it
- Separate persisted `rule_result.json`, `agent_assessment.json`, `decision_result.json`, and `execution_trace.json`

## 外部検証

- Claude Desktop Cowork 3P Sign in with AWS and Plugin browser path reached on a separate PC.
- Remote HTTPS MCP v2 smoke and What-if scenario comparison verified after deploy.

## 既知の制約

- `APP_MODE=mock` では実アップロードPDFを抽出しない。fixture demo casesのみ査定完了する。
- `AUTH_MODE=none` はdemo環境だけ許可。公開HTTPS環境では `AUTH_MODE=jwt` を使う。
