# Self-Serve MCP/MCPB Design Handoff

Last updated: 2026-06-21.

This document is for an external GPT or designer who will design a
kintone-like self-serve MCP/MCPB creation experience. It summarizes what is
already implemented in this project, what can be reused, and what is not yet
implemented.

このドキュメントは、kintone のような self-serve MCP/MCPB 作成体験を外部 GPT や設計者に検討してもらうための引き継ぎ資料です。このプロジェクトで実装済みの範囲、再利用できる部品、未実装の範囲をまとめます。

## Executive Summary

The current project is not yet a self-serve MCP builder. It is a working,
domain-specific underwriting support MCP with:

- a deployed HTTPS Remote MCP endpoint;
- AWS-backed asynchronous assessment workflow;
- skill-only Claude organization Plugin distribution;
- deterministic rule engine;
- scenario comparison;
- evidence-backed agent findings;
- deploy and distribution scripts for Cowork 3P demos.

The strongest reusable foundation for a self-serve MCP/MCPB product is the
separation between:

1. domain logic in `underwriting_core/`;
2. service orchestration in `underwriting_app/`;
3. MCP transport in `underwriting_mcp/`;
4. deploy/distribution assets in `infra/`, `deploy/cowork/`, and `plugin/`.

現状は self-serve MCP builder ではありません。実装済みなのは、保険引受査定に特化した Remote MCP です。ただし、domain logic、service orchestration、MCP transport、deploy/distribution が分離されているため、self-serve 化の土台として再利用できます。

## Live Environment

Current deployed demo endpoint:

```text
https://<MCP_HOST>/mcp
```

Current AWS deployment shape:

- AWS account: `<AWS_ACCOUNT_ID>`
- Region: `ap-northeast-1`
- Deployment mode: `demo-low-cost`
- Public HTTPS ALB in front of ECS Fargate MCP server
- Workflow Lambda + Step Functions + S3 + DynamoDB + KMS
- WAF currently disabled in low-cost mode
- JWT auth enabled for public MCP

現在のデモ環境は、東京リージョンの low-cost demo 構成です。HTTPS ALB の裏に ECS Fargate MCP サーバがあり、査定 workflow は Lambda / Step Functions / S3 / DynamoDB / KMS を使います。公開 MCP は JWT 認証です。

## Implemented MCP Server Capabilities

Implemented MCP tools:

```text
create_underwriting_case
start_underwriting_review
get_underwriting_review
explain_underwriting_review
simulate_underwriting_change
list_demo_cases
```

Implemented MCP resources:

```text
underwriting://cases/{case_id}/result
underwriting://cases/{case_id}/evidence
underwriting://rulesets/{ruleset_version}
```

Implemented non-MCP upload endpoint:

```text
POST /v1/cases/{case_id}/documents/{document_type}
```

Important behavior:

- MCP uses Streamable HTTP at `/mcp`.
- Public MCP uses bearer JWT.
- File upload uses separate short-lived single-use upload tokens.
- Business errors are structured and do not expose stack traces.
- Upload validation checks PDF signature, MIME, encryption, size, page count, and filename safety.

実装済み MCP tool は上記の 6 つです。PDF アップロードは MCP tool ではなく `/v1/cases/{case_id}/documents/{document_type}` の HTTP endpoint です。MCP 認証と upload token は分離されています。

## Implemented Underwriting Domain Features

Implemented domain behavior:

- canonical facts model;
- deterministic rule engine;
- ruleset loader from YAML;
- result assembly;
- evidence tracking by document/page/value;
- missing information;
- contradictions;
- V2 recommendation categories:
  - `ELIGIBLE_CANDIDATE`
  - `REFER_INFO_REQUEST`
  - `REFER_MEDICAL_REVIEW`
  - `REFER_SENIOR_REVIEW`
  - `DECLINE_CANDIDATE`
- scenario override validation with fixed allowed paths;
- What-if comparison;
- deterministic `agent_findings` for ambiguous free text;
- Japanese summary generation by Bedrock, without allowing Bedrock to change deterministic recommendation.

Implemented rulesets:

```text
rulesets/demo-medical-2026-01
rulesets/demo-medical-2026-02
```

Implemented demo cases:

```text
samples/case-a  clean eligible case
samples/case-b  disclosure/exam mismatch case
samples/case-c  senior/medical review risk case
samples/case-d  ambiguous free-text agent finding case
```

実装済みの domain 機能は、canonical facts、決定論 rule engine、YAML ruleset、evidence、contradiction、missing information、What-if、agent findings です。Bedrock は説明文生成に使えますが、deterministic recommendation を変更できない設計です。

## Implemented Claude/Cowork Distribution

Implemented distribution model:

- Cowork 3P inference through AWS Bedrock Claude.
- Remote MCP distributed via `managedMcpServers`.
- Claude organization Plugin is skill-only.
- Plugin intentionally contains no `.mcp.json` and no MCP secret.
- `.mobileconfig` for macOS and `.reg` for Windows can be generated.
- Mac and Windows install scripts exist.
- Windows simple handoff zip exists.

Important paths:

```text
plugin/underwriting-review/
deploy/cowork/
deploy/cowork/render_config.py
deploy/cowork/macos/install-demo.sh
deploy/cowork/windows/install-demo.ps1
install-windows-demo.ps1
WINDOWS_HANDOFF_FOR_CHATGPT.md
dist/cowork-windows-simple.zip
```

Claude / Cowork 配布は実装済みです。Remote MCP 接続情報は `managedMcpServers` 側に置き、Plugin は skill-only にしています。Windows 向け簡易 zip もあります。

## Implemented AWS Infrastructure

Implemented CDK stacks:

```text
infra/lib/network-stack.ts
infra/lib/data-stack.ts
infra/lib/workflow-stack.ts
infra/lib/mcp-stack.ts
```

Implemented infrastructure:

- VPC and low-cost public-subnet demo mode;
- S3 artifact bucket;
- KMS key;
- DynamoDB job/case table;
- Docker Lambda worker for workflow steps;
- Step Functions state machine;
- ECS Fargate MCP server;
- HTTPS ALB;
- optional Route 53 alias;
- optional WAF;
- Secrets Manager JWT secret.

Deployment modes:

- default/private: production-like boundary with VPC endpoints;
- `demo-low-cost`: lower cost, no Interface VPC Endpoints, Lambda outside VPC, ECS public subnets behind ALB.

AWS CDK による infra は実装済みです。本番相当の private mode と、デモ用 low-cost mode があります。

## Implemented Tests And Gates

Current verified gates:

```bash
make test
make lint
make typecheck
make verify-data-boundary
npm run build
```

Current test count:

```text
77 passed
```

Live verification already completed:

- remote v2 smoke test succeeded;
- Case A high blood pressure/treatment/medication What-if:
  - `ELIGIBLE_CANDIDATE` -> `REFER_MEDICAL_REVIEW`;
- Case A ambiguous disclosure free-text What-if:
  - `ELIGIBLE_CANDIDATE` -> `REFER_INFO_REQUEST`;
  - added finding: `AGENT-FREE-TEXT-001`.

テストと検証は整備済みです。local test、lint、typecheck、data-boundary check、TypeScript build が通っています。remote MCP でも v2 smoke と What-if 検証済みです。

## Key Internal Boundaries

The existing code is intentionally layered:

| Layer | Path | Responsibility |
|---|---|---|
| Domain core | `underwriting_core/` | facts, rules, agent findings, result assembly, what-if |
| App service | `underwriting_app/` | cases, jobs, ports, orchestration, upload validation |
| MCP transport | `underwriting_mcp/` | FastMCP server, JWT auth, HTTP upload API |
| Workflow worker | `lambdas/underwriting_workflow/` | Textract/Bedrock normalization and result assembly in AWS |
| Infra | `infra/` | CDK stacks |
| Distribution | `deploy/cowork/`, `plugin/` | Cowork config and Claude Plugin |
| Fixtures/tests | `samples/`, `tests/` | demo cases and regression tests |

Self-serve MCP/MCPB design should preserve this separation. Avoid putting domain rules, tenant configuration, MCP transport, and deploy packaging into one large module.

self-serve 化する場合も、この責務分離は維持してください。domain rules、tenant config、MCP transport、deploy packaging を 1 つの巨大 module に混ぜない方がよいです。

## What Is Not Implemented Yet

The following are not implemented:

- self-serve UI for creating MCPs/MCPBs;
- tenant/project model;
- user/team/role management;
- browser-based connector builder;
- schema/ruleset editor UI;
- form designer;
- workflow designer;
- plugin/package marketplace;
- one-click deploy per tenant;
- versioned MCP template catalog;
- OAuth/Cognito production auth;
- production token issuer / headers helper;
- billing, quotas, limits, usage metering;
- audit dashboard;
- multi-tenant isolation model;
- remote sandbox execution for arbitrary user-defined connectors;
- connector secret vault UI;
- policy approval workflow;
- rollback UI;
- import/export of MCP definitions;
- generated docs for each self-serve MCP;
- Bedrock-backed general agent assessment replacing deterministic local detector;
- separate persisted `rule_result.json`, `agent_assessment.json`, `decision_result.json`, and `execution_trace.json`.

現時点では self-serve UI、tenant 管理、コネクタ builder、schema/ruleset editor、marketplace、one-click deploy、billing、multi-tenant isolation などは未実装です。

## Reusable Pieces For A Self-Serve MCP/MCPB Builder

Good candidates for reuse:

- FastMCP server assembly pattern in `underwriting_mcp/server.py`;
- structured error envelope in `underwriting_app/errors.py`;
- upload/session token model in `underwriting_app/models.py` and `underwriting_app/service.py`;
- YAML ruleset pattern under `rulesets/`;
- Pydantic schema generation in `scripts/generate_schemas.py`;
- regression gate pattern in `tests/`;
- plugin/cowork packaging pattern in `deploy/cowork/` and `plugin/`;
- CDK low-cost demo deployment mode;
- data-boundary verifier in `scripts/verify_data_boundary.py`.

Reusing these pieces is preferable to designing the self-serve product from a blank page.

self-serve MCP/MCPB builder では、FastMCP server 組み立て、structured error、upload/session token、YAML ruleset、Pydantic schema generation、regression tests、Cowork packaging、CDK low-cost deploy、data-boundary verifier を再利用候補にできます。

## Suggested Self-Serve Design Axes

An external design should decide these product boundaries explicitly:

1. Is MCPB a project bundle, a deployable MCP service, a Claude Plugin package, or all of these?
2. Is the target user a business admin, developer, solution architect, or internal platform team?
3. Does self-serve mean configuration-only, code-generation, or hosted runtime provisioning?
4. Are connectors limited to approved templates, or can users define arbitrary tools?
5. Where are secrets stored and rotated?
6. How are test fixtures and golden regression tests generated per MCP?
7. What is the promotion flow: draft -> test -> review -> publish -> deploy -> rollback?
8. How is data boundary verified before publishing?
9. How are cost controls applied per tenant/project?
10. How are MCP tool schemas, Plugin skills, and Cowork managed settings versioned together?

外部設計では、MCPB の意味、対象ユーザー、設定だけなのか code generation まで含むのか、任意 tool を許可するのか、secret 管理、test fixture、publish/deploy/rollback、data boundary、コスト制御、versioning を明示的に決める必要があります。

## Recommended First Self-Serve MVP

Do not start with a fully generic MCP marketplace. A safer first MVP is:

```text
Template-based MCPB builder for approved internal demo workflows
```

Recommended MVP scope:

- create project from template;
- edit display name, description, allowed tools, and environment parameters;
- upload sample fixtures;
- define tool input/output schemas from Pydantic/JSON Schema;
- generate skill-only Claude Plugin;
- generate Cowork managed MCP config;
- run local contract tests;
- run data-boundary verifier;
- package Windows/Mac handoff bundle;
- deploy to a low-cost demo AWS environment;
- show endpoint, token expiry, smoke status, and rollback target.

First template:

```text
underwriting-review
```

This uses the current project as the seed template.

最初から汎用 marketplace を作るのはスコープが広すぎます。最初の MVP は「承認済み社内デモ workflow 向け template-based MCPB builder」がよいです。現在の `underwriting-review` を seed template にできます。

## Non-Negotiable Guardrails

For any self-serve design, keep these guardrails:

- generated Plugin must not contain `.mcp.json` or MCP secrets;
- public Remote MCP must use HTTPS;
- public Remote MCP must not run with `AUTH_MODE=none`;
- upload tokens must stay short-lived and scoped;
- every generated MCP must have contract tests;
- every generated MCP must have a data-boundary check;
- every generated MCP must have a rollback path;
- business outputs should distinguish final decisions from decision support;
- LLM output must not silently override deterministic guardrails.

self-serve 化しても、Plugin に secret を入れない、HTTPS 必須、公開 MCP の `AUTH_MODE=none` 禁止、短命 upload token、contract tests、data-boundary check、rollback、最終判断と支援結果の区別、LLM が guardrail を黙って上書きしないことは必須です。

## Current Verification Commands

Use these commands to confirm the current implementation remains healthy:

```bash
cd /Users/ikedamasahiro/Agentmemory_MVP/underwriting-mcp
make test
make lint
make typecheck
make verify-data-boundary
npm run build
```

Live smoke after deploy:

```bash
AWS_PROFILE=ikeda \
AWS_REGION=ap-northeast-1 \
MCP_URL=https://<MCP_HOST>/mcp \
MCP_JWT_SECRET_ID=<MCP_JWT_SECRET_ID> \
RULESET_VERSION=demo-medical-2026-02 \
RUN_AWS_LIVE_TESTS=1 \
make smoke-test
```

