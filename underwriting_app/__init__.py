"""MCP アプリケーション層。

決定論ドメインロジック（``underwriting_core``、AWS 非依存）の上に、ケース/ジョブ
管理・ポート（外部システム抽象）・モックアダプタ・6 つの MCP tool 操作を実装する。
AWS 実装（Textract / Bedrock / Step Functions / DynamoDB / S3）はポートの差し替えで
追加できるようにし、ドメインロジックには IO を持ち込まない。
"""
