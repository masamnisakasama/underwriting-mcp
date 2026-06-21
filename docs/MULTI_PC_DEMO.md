# Multi PC Demo

This checklist verifies that Claude Desktop on another PC can use Cowork
third-party inference and call the deployed HTTPS MCP server.

このチェックリストは、別PCの Claude Desktop が Cowork サードパーティ推論を使い、デプロイ済みの HTTPS MCP サーバーを呼び出せることを確認するためのものです。

## Current Demo Endpoint

Use the deployed MCP endpoint below:

以下のデプロイ済み MCP エンドポイントを使います。

```text
https://<MCP_HOST>/mcp
```

The server is already smoke-tested from the admin environment. The remaining
validation is whether a separate Claude Desktop PC can authenticate with AWS,
load the organization Plugin, and call the managed Remote MCP connector.

サーバーは管理環境からの smoke test 済みです。残りの確認は、別PCの Claude Desktop が AWS 認証を完了し、組織 Plugin を読み込み、管理された Remote MCP connector を呼べるかどうかです。

## Admin PC Preparation

Run these steps on the source/admin PC under this project directory.

以下は元PC、つまり管理用PCで、このプロジェクトディレクトリ配下で実行します。

```bash
cd /Users/ikedamasahiro/Agentmemory_MVP/underwriting-mcp
export AWS_PROFILE=ikeda
export AWS_REGION=ap-northeast-1
```

Generate a short-lived demo MCP token:

短命のデモ MCP トークンを発行します。

```bash
export DEMO_MCP_TOKEN="$(
  .venv/bin/python scripts/issue_demo_mcp_token.py \
    --secret-id <MCP_JWT_SECRET_ID> \
    --subject cowork-demo-pc \
    --ttl-seconds 86400
)"
```

Render the Cowork 3P managed configuration. Replace the SSO placeholders with
the values for the AWS IAM Identity Center environment used by the demo user.

Cowork 3P の管理設定を生成します。SSO プレースホルダーは、デモユーザーが使う AWS IAM Identity Center 環境の値に置き換えてください。

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

Package the skill-only Plugin:

skill-only Plugin をパッケージ化します。

```bash
make package-plugin
```

## Transfer To The Demo PC

Transfer the following files or directories to the other PC:

以下のファイルまたはディレクトリを別PCへ転送します。

```text
plugin/underwriting-review/
deploy/cowork/generated/
deploy/cowork/macos/
deploy/cowork/windows/
samples/case-a/
```

The generated files contain a short-lived bearer token. Treat them as demo
secrets and avoid committing them or sending them to unrelated users.

生成ファイルには短命 bearer token が含まれます。デモ用シークレットとして扱い、コミットしたり無関係なユーザーへ送ったりしないでください。

## Install On macOS

Install Claude Desktop first. Then run this from the copied project directory:

先に Claude Desktop をインストールします。その後、コピーしたプロジェクトディレクトリから以下を実行します。

```bash
sudo bash deploy/cowork/macos/install-demo.sh
```

If macOS asks for profile approval, approve the installed configuration profile
in System Settings. Then fully quit and restart Claude Desktop.

macOS がプロファイル承認を求めた場合は、システム設定でインストールされた構成プロファイルを承認してください。その後、Claude Desktop を完全終了して再起動します。

## Install On Windows

Install Claude Desktop first. Then open PowerShell as Administrator from the
copied project directory:

先に Claude Desktop をインストールします。その後、コピーしたプロジェクトディレクトリから PowerShell を管理者として開きます。

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\deploy\cowork\windows\install-demo.ps1
```

After the registry import completes, fully quit and restart Claude Desktop.

レジストリの取り込みが完了したら、Claude Desktop を完全終了して再起動します。

## Claude Desktop Validation

On the demo PC, validate this flow:

デモPCで以下の流れを確認します。

1. Claude Desktop starts in Cowork third-party inference mode.
2. The first run shows Sign in with AWS.
3. AWS IAM Identity Center opens in the OS browser and completes login.
4. Built-in `WebSearch` and `WebFetch` are disabled.
5. The managed connector `underwriting-decision` is visible.
6. The Plugin browser shows `Underwriting Review`.
7. Installing the Plugin exposes `review-case` and `compare-scenario` skills.
8. The Plugin directory does not contain `.mcp.json`.
9. Running `/underwriting-review:review-case` uploads PDFs to the AWS MCP hostname, not to Anthropic APIs.
10. The returned report includes recommendation, rule hits, evidence pages, missing information, contradictions, and the demo disclaimer.

1. Claude Desktop が Cowork サードパーティ推論モードで起動する。
2. 初回実行時に Sign in with AWS が表示される。
3. AWS IAM Identity Center が OS ブラウザで開き、ログインが完了する。
4. 組み込みの `WebSearch` と `WebFetch` が無効化されている。
5. 管理 connector `underwriting-decision` が見える。
6. Plugin browser に `Underwriting Review` が表示される。
7. Plugin をインストールすると `review-case` と `compare-scenario` skill が使える。
8. Plugin ディレクトリに `.mcp.json` が含まれていない。
9. `/underwriting-review:review-case` を実行すると、PDF が Anthropic API ではなく AWS MCP ホスト名へアップロードされる。
10. 返却レポートに recommendation、rule hits、evidence pages、missing information、contradictions、demo disclaimer が含まれる。

## Expected Demo Result

Use the PDFs in `samples/case-a/` for the first run. A successful run should
complete the underwriting workflow and return an eligible-candidate style
recommendation.

初回実行では `samples/case-a/` の PDF を使います。成功時は underwriting workflow が完了し、引受候補相当の recommendation が返ります。

```text
ELIGIBLE_CANDIDATE
```

## Troubleshooting

If the MCP call returns `401`, the demo token is expired or the generated
configuration was not applied. Regenerate the token, render the configuration
again, reinstall it on the demo PC, and restart Claude Desktop.

MCP 呼び出しが `401` を返す場合、デモトークンが期限切れか、生成設定が適用されていません。トークンを再発行し、設定を再生成して、デモPCへ再インストールし、Claude Desktop を再起動してください。

If AWS sign-in fails, check the SSO start URL, SSO region, permission set name,
and whether the demo user is assigned to the target AWS account.

AWS サインインが失敗する場合は、SSO start URL、SSO region、permission set name、およびデモユーザーが対象 AWS アカウントへ割り当てられているかを確認してください。

If the Plugin is not visible, confirm that `plugin/underwriting-review` was
copied to the system-wide Claude Desktop organization plugin directory by the
installer script, then restart Claude Desktop.

Plugin が見えない場合は、インストーラスクリプトによって `plugin/underwriting-review` が Claude Desktop のシステム全体の組織 Plugin ディレクトリへコピーされたか確認し、Claude Desktop を再起動してください。

If the connector is not visible, confirm that the generated `.mobileconfig` or
`.reg` file was installed and that it contains `<MCP_HOST>`.

connector が見えない場合は、生成された `.mobileconfig` または `.reg` がインストール済みで、その中に `<MCP_HOST>` が含まれているか確認してください。
