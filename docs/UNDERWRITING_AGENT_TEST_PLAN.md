# Underwriting Agent Test And Regression Plan

Last updated: 2026-06-21.

## Test Strategy

The demo should be protected by layered tests. Each layer has a different job:

1. Unit tests protect pure rule, composer, and agent-finding logic.
2. Integration tests protect Case A/B/C and What-if workflows.
3. Contract tests protect MCP tool schemas and error envelopes.
4. Live smoke tests protect the deployed HTTPS MCP path.

このデモは層ごとのテストで守る。unit は純粋ロジック、integration は fixture workflow、contract は MCP schema、live smoke は deploy 済み HTTPS MCP を守る。

## Golden Cases

| Case | Purpose | Expected |
|---|---|---|
| Case A | Clean STP-like demo case | `ELIGIBLE_CANDIDATE`, no agent findings |
| Case B | Disclosure/exam mismatch and missing treatment status | referral remains required, contradiction and missing info visible |
| Case C | Senior/medical risk fixture | senior/medical referral signals are preserved |
| Case D | Ambiguous free-text only | `REFER_INFO_REQUEST`, agent finding present, no deterministic medical rule hit required |
| What-if A1 | Case A + BP 165/105 + treatment + medication | `REFER_MEDICAL_REVIEW`, recommendation changed |
| What-if A2 | Case A + ambiguous free text only | `REFER_INFO_REQUEST`, recommendation changed because of agent finding |
| What-if invalid path | Bad override such as `health.bp.systolic` | structured fail-fast error |

## Regression Gates

The following failures must block completion:

- Case A stops returning `ELIGIBLE_CANDIDATE`.
- High-BP+treatment+medication What-if does not change to `REFER_MEDICAL_REVIEW`.
- Ambiguous free text does not create an `agent_findings` item.
- An agent finding lowers a deterministic guardrail outcome.
- A finding lacks source text or evidence reference.
- Invalid scenario path is silently accepted.
- MCP structured output schema drifts without regenerated schemas.
- Plugin skill starts with a stale ruleset version.

## Commands

Run these before claiming the implementation is complete:

```bash
make test
make lint
make typecheck
make verify-data-boundary
npm run build
```

Run live verification after deploy when AWS is in scope:

```bash
AWS_PROFILE=ikeda \
AWS_REGION=ap-northeast-1 \
MCP_URL=https://<MCP_HOST>/mcp \
MCP_JWT_SECRET_ID=<MCP_JWT_SECRET_ID> \
RULESET_VERSION=demo-medical-2026-02 \
RUN_AWS_LIVE_TESTS=1 \
make smoke-test
```

## Artifact Expectations

For each completed assessment, the implementation should be able to expose or
persist:

- `canonical_facts`
- `rule_result`
- `agent_assessment`
- `decision_result`
- final `UnderwritingResult`

For this slice, `agent_assessment` may be deterministic in local/mock mode and
Bedrock-backed in AWS mode later. The result schema must still expose
`agent_findings` so report and regression tests can depend on it.

この slice では、local/mock の `agent_assessment` は決定論的でよい。AWS mode で Bedrock backed にするのは後続でもよい。ただし result schema には `agent_findings` を出し、report と regression test が依存できるようにする。

