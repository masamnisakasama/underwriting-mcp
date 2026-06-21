# Troubleshooting

- `UNAUTHORIZED`: refresh the short-lived MCP token in managed configuration.
- `UPLOAD_TOKEN_EXPIRED`: create a new case and upload again.
- `UPLOAD_TOKEN_ALREADY_USED`: create a new case; upload tokens are single-use.
- `PAGE_LIMIT_EXCEEDED`: keep each PDF under 20 pages and the case under 30 pages.
- `NOT_AVAILABLE_IN_MODE`: local mock mode only processes fixture demo cases. Use AWS mode for real uploaded PDFs.
- AWS CLI `Token has expired`: run `aws sso login --profile <profile>` and re-run deploy or smoke.
- Smoke test `MCP_URL and MCP_BEARER_TOKEN are required`: export both variables before `RUN_AWS_LIVE_TESTS=1 make smoke-test`.
- Workflow remains `PROCESSING`: inspect Step Functions execution and CloudWatch Logs for `UnderwritingWorkflowWorker`; failed executions should mark the job `FAILED`.
