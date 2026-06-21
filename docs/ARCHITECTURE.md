# Architecture

Draw.io overview: [`underwriting-mcp-architecture.drawio`](underwriting-mcp-architecture.drawio)

V2 uses an internet-facing HTTPS Application Load Balancer with AWS WAF in front of an ECS Fargate MCP gateway.
ECS tasks, Lambda, Step Functions, S3, DynamoDB, KMS, and Bedrock access are private AWS-side resources.

Remote MCP distribution is managed by Cowork `managedMcpServers`.
The organization Plugin is skill-only and provides user workflow instructions plus the upload helper script.

Long-running underwriting review is asynchronous:

1. `create_underwriting_case`
2. Upload PDFs to `/v1/cases/{case_id}/documents/{document_type}`
3. `start_underwriting_review`
4. Poll `get_underwriting_review`
5. Optional `explain_underwriting_review` and `simulate_underwriting_change`
