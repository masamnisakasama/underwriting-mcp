# Deploy

Local demo:

```bash
make install
make generate-samples
make dev-mcp
```

AWS deployment uses CDK v2 assets in `infra/`.
Set at least:

- `certificateArn`
- `hostedZoneName`
- `mcpHostName`
- `bedrockModelId` or inference profile ARN
- `mcpJwtSecretArn`
- Optional `hostedZoneName` for Route 53 alias record creation

Public access must terminate TLS at the ALB. In the default private mode, backend tasks must not
receive public IP addresses.

For the lowest-cost live demo, use `-c deploymentMode=demo-low-cost`. This mode is intended for
fictional demo forms only:

- does not create Interface VPC Endpoints
- runs the workflow Lambda outside the VPC
- uses deterministic demo extraction instead of Textract because Textract is not available in
  `ap-northeast-1`
- runs the MCP Fargate task in public subnets with a public IP
- keeps the internet-facing ALB for HTTPS, ACM, and stable DNS
- disables WAF by default; add `-c enableWaf=true` to keep the rate-limit Web ACL

This removes the main monthly cost driver from the private demo architecture. Use the default
private mode for a more production-like boundary.

Deploy:

```bash
npm install
npm run build
npm run synth -- \
  -c certificateArn=<ACM_CERTIFICATE_ARN> \
  -c mcpHostName=<MCP_HOSTNAME> \
  -c bedrockModelId=<BEDROCK_MODEL_OR_PROFILE_ID>
npm run deploy -- \
  -c bedrockModelId=<BEDROCK_MODEL_OR_PROFILE_ID> \
  -c certificateArn=<ACM_CERTIFICATE_ARN> \
  -c mcpHostName=<MCP_HOSTNAME> \
  -c hostedZoneName=<HOSTED_ZONE_NAME>
```

Low-cost demo deploy:

```bash
npm run deploy -- \
  -c deploymentMode=demo-low-cost \
  -c bedrockModelId=<BEDROCK_MODEL_OR_PROFILE_ID> \
  -c certificateArn=<ACM_CERTIFICATE_ARN> \
  -c mcpHostName=<MCP_HOSTNAME> \
  -c hostedZoneName=<HOSTED_ZONE_NAME>
```

Issue a demo MCP token:

```bash
export DEMO_MCP_TOKEN="$(
  python scripts/issue_demo_mcp_token.py \
    --secret-id <McpJwtSecretName-output-or-secret-arn> \
    --subject demo-user
)"
```

Render Cowork settings:

```bash
python deploy/cowork/render_config.py \
  --aws-account-id "$AWS_ACCOUNT_ID" \
  --bedrock-region "$AWS_REGION" \
  --sso-start-url "$AWS_SSO_START_URL" \
  --sso-region "$AWS_SSO_REGION" \
  --permission-set-name "$AWS_PERMISSION_SET_NAME" \
  --bedrock-inference-profile-id "$BEDROCK_MODEL_ID" \
  --mcp-host "$MCP_HOST" \
  --demo-mcp-token "$DEMO_MCP_TOKEN" \
  --organization-uuid "$ORG_UUID"
```

Run live smoke:

```bash
export MCP_URL="https://${MCP_HOST}/mcp"
export MCP_BEARER_TOKEN="$DEMO_MCP_TOKEN"
# Or set MCP_JWT_SECRET_ID=<McpJwtSecretName-output-or-secret-arn> and let smoke issue a token.
make check-live-prereqs
RUN_AWS_LIVE_TESTS=1 make smoke-test
```

The smoke test creates a case, uploads the generated sample PDFs, starts the workflow, polls until completion, and checks the recommendation against `expected-result.json`.
