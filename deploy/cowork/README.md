# Cowork 3P Demo Distribution

This directory contains the files used to distribute the Claude Desktop Cowork
third-party inference demo to another PC. V2 uses `managedMcpServers` as the
source of truth for the Remote MCP connector. The organization Plugin is
skill-only and intentionally contains no `.mcp.json` file and no MCP secret.

このディレクトリには、Claude Desktop の Cowork サードパーティ推論デモを別PCへ配布するためのファイルが入っています。V2 では Remote MCP 接続の正本を `managedMcpServers` に置きます。組織 Plugin は skill-only で、意図的に `.mcp.json` や MCP シークレットを含めません。

## Live Demo Values

Use these values for the current deployed demo environment:

現在デプロイ済みのデモ環境では、以下の値を使います。

```text
AWS account ID: <AWS_ACCOUNT_ID>
AWS region: ap-northeast-1
MCP host: <MCP_HOST>
MCP URL: https://<MCP_HOST>/mcp
MCP JWT secret ID: <MCP_JWT_SECRET_ID>
Bedrock inference profile ID: jp.anthropic.claude-sonnet-4-5-20250929-v1:0
```

The SSO start URL, SSO region, and permission set name must match the AWS IAM
Identity Center setup used by the demo user.

SSO start URL、SSO region、permission set name は、デモユーザーが使う AWS IAM Identity Center の設定に合わせてください。

## Generate A Demo MCP Token

Run this on the admin/source PC where AWS SSO profile `ikeda` is already logged
in. The token is short-lived and is embedded only in the generated managed
configuration, not in the Plugin.

これは AWS SSO プロファイル `ikeda` でログイン済みの管理元PCで実行します。トークンは短命で、Plugin ではなく生成された管理設定のみに埋め込まれます。

```bash
cd /Users/ikedamasahiro/Agentmemory_MVP/underwriting-mcp
export AWS_PROFILE=ikeda
export AWS_REGION=ap-northeast-1

export DEMO_MCP_TOKEN="$(
  .venv/bin/python scripts/issue_demo_mcp_token.py \
    --secret-id <MCP_JWT_SECRET_ID> \
    --subject cowork-demo-pc \
    --ttl-seconds 86400
)"
```

`86400` seconds is 24 hours. If Claude Desktop later receives `401`
responses from the MCP server, generate a new token and render the
configuration again.

`86400` 秒は24時間です。後で Claude Desktop が MCP サーバーから `401` を返された場合は、トークンを再発行して設定を再生成してください。

## Render Cowork Configuration

Replace the three SSO placeholders with the actual values for the demo AWS
Identity Center environment.

3つの SSO プレースホルダーは、デモ用 AWS Identity Center 環境の実値に置き換えてください。

```bash
export ORG_UUID="$(uuidgen | tr '[:upper:]' '[:lower:]')"

.venv/bin/python deploy/cowork/render_config.py \
  --aws-account-id <AWS_ACCOUNT_ID> \
  --bedrock-region ap-northeast-1 \
  --sso-start-url "<AWS_SSO_START_URL>" \
  --sso-region "<AWS_SSO_REGION>" \
  --permission-set-name "<PERMISSION_SET_NAME>" \
  --bedrock-inference-profile-id "jp.anthropic.claude-sonnet-4-5-20250929-v1:0" \
  --mcp-host "<MCP_HOST>" \
  --demo-mcp-token "$DEMO_MCP_TOKEN" \
  --organization-uuid "$ORG_UUID"
```

The generated files are written to `deploy/cowork/generated/`:

生成ファイルは `deploy/cowork/generated/` に出力されます。

```text
cowork-3p-demo.json
cowork-3p-demo.mobileconfig
cowork-3p-demo.reg
```

Do not commit or broadly share generated files because they contain a
short-lived bearer token for the demo MCP server.

生成ファイルにはデモ MCP サーバー用の短命 bearer token が含まれるため、コミットしたり広く共有したりしないでください。

## Package The Plugin

The Plugin package contains only skills and metadata. It does not contain MCP
credentials.

Plugin パッケージには skill とメタデータのみが含まれます。MCP 認証情報は含まれません。

```bash
make package-plugin
```

This writes:

以下が生成されます。

```text
dist/underwriting-review-plugin.zip
```

The installer scripts copy the unpacked Plugin from `plugin/underwriting-review`
into the system-wide Claude Desktop organization plugin directory. For another
PC, transfer either the repository subset needed by the installer or the full
project directory.

インストーラスクリプトは、展開済みの `plugin/underwriting-review` を Claude Desktop のシステム全体の組織 Plugin ディレクトリへコピーします。別PCへは、インストーラーに必要なリポジトリの一部、またはプロジェクトディレクトリ全体を転送してください。

## Install On Another PC

On macOS, run this from the copied project directory:

macOS では、コピーしたプロジェクトディレクトリから以下を実行します。

```bash
sudo bash deploy/cowork/macos/install-demo.sh
```

On Windows, run PowerShell as Administrator from the copied project directory:

Windows では、コピーしたプロジェクトディレクトリから PowerShell を管理者として開き、以下を実行します。

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\deploy\cowork\windows\install-demo.ps1
```

Restart Claude Desktop after installing the configuration and Plugin.

設定と Plugin のインストール後、Claude Desktop を再起動してください。

## Data Boundary

The managed MCP configuration points Claude Desktop to:

管理 MCP 設定は Claude Desktop に以下の接続先を渡します。

```text
https://<MCP_HOST>/mcp
```

The Plugin directory must not contain `.mcp.json`, AWS credentials, long-lived
access keys, or MCP secrets. The remote MCP bearer token belongs in the
generated managed configuration only.

Plugin ディレクトリには `.mcp.json`、AWS 認証情報、長期アクセスキー、MCP シークレットを入れてはいけません。Remote MCP の bearer token は生成された管理設定にのみ入れます。

Required egress endpoints are based on Claude Desktop's third-party inference
egress report. The template includes the core hosts, but the exported Claude
Desktop configuration is authoritative.

必要な外向き通信先は Claude Desktop のサードパーティ推論 egress report に基づきます。テンプレートには主要ホストを含めていますが、最終的には Claude Desktop からエクスポートされた設定を正とします。
