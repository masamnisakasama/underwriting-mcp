# Windows Handoff For ChatGPT

I have a zip file named `cowork-windows-simple.zip`. It contains a Claude
Desktop Cowork third-party inference demo and an organization Plugin named
`Underwriting Review`.

Please help me install and validate it on a Windows PC.

## What To Do

1. Copy `cowork-windows-simple.zip` to the Windows PC.
2. Right-click the zip and choose `Extract All`.
3. Open the extracted folder.
4. Right-click PowerShell and choose `Run as administrator`.
5. In PowerShell, move into the extracted folder.
6. Run:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\install-windows-demo.ps1
```

7. Fully quit and restart Claude Desktop.
8. In Claude Desktop, sign in with AWS when prompted.
9. Complete AWS SSO login in the browser.
10. Open the Plugin browser and enable `Underwriting Review`.
11. Run `/underwriting-review:review-case`.
12. Use the sample PDFs in `samples\case-a`.

## Expected Files In The Extracted Folder

The extracted folder should contain:

```text
install-windows-demo.ps1
deploy\cowork\generated\cowork-3p-demo.reg
deploy\cowork\windows\install-demo.ps1
plugin\underwriting-review\
samples\case-a\
```

If `deploy\cowork` is missing, the zip was not extracted correctly or the wrong
zip was used. Use `cowork-windows-simple.zip`, not only
`underwriting-review-plugin.zip`.

## Expected Result

The demo should call:

```text
https://<MCP_HOST>/mcp
```

A successful underwriting demo should return an eligible-candidate style result:

```text
ELIGIBLE_CANDIDATE
```

## Troubleshooting

If PowerShell says the script is blocked, run:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

If the installer says Administrator is required, close PowerShell and open it
again with `Run as administrator`.

If Claude Desktop returns `401` from MCP, the demo token is expired. Ask the
admin Mac owner to regenerate the Cowork config and send a new zip.

If `Underwriting Review` is not visible in Claude Desktop, rerun the installer
as Administrator and restart Claude Desktop.

---

# ChatGPT に渡す Windows 引き継ぎ書

`cowork-windows-simple.zip` という zip ファイルがあります。この中には Claude
Desktop の Cowork サードパーティ推論デモと、`Underwriting Review` という組織
Plugin が入っています。

Windows PC でのインストールと動作確認を手伝ってください。

## やること

1. `cowork-windows-simple.zip` を Windows PC にコピーします。
2. zip を右クリックして `Extract All` / `すべて展開` を選びます。
3. 展開されたフォルダを開きます。
4. PowerShell を右クリックして `管理者として実行` します。
5. PowerShell で展開フォルダへ移動します。
6. 以下を実行します。

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\install-windows-demo.ps1
```

7. Claude Desktop を完全終了して再起動します。
8. Claude Desktop で求められたら AWS でサインインします。
9. ブラウザで AWS SSO ログインを完了します。
10. Plugin browser を開き、`Underwriting Review` を有効化します。
11. `/underwriting-review:review-case` を実行します。
12. `samples\case-a` のサンプル PDF を使います。

## 展開後にあるべきファイル

展開フォルダには以下があるはずです。

```text
install-windows-demo.ps1
deploy\cowork\generated\cowork-3p-demo.reg
deploy\cowork\windows\install-demo.ps1
plugin\underwriting-review\
samples\case-a\
```

`deploy\cowork` が無い場合は、zip の展開に失敗しているか、違う zip を使っています。
`underwriting-review-plugin.zip` ではなく、`cowork-windows-simple.zip` を使ってください。

## 期待結果

デモは以下の MCP を呼び出します。

```text
https://<MCP_HOST>/mcp
```

成功すると、引受候補相当の結果が返ります。

```text
ELIGIBLE_CANDIDATE
```

## トラブルシュート

PowerShell でスクリプトがブロックされた場合は、以下を実行します。

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

Administrator が必要と言われた場合は、PowerShell を閉じて、`管理者として実行`
で開き直してください。

Claude Desktop が MCP から `401` を返す場合は、デモトークンの期限切れです。
管理元の Mac で Cowork 設定を再生成し、新しい zip を送ってもらってください。

Claude Desktop に `Underwriting Review` が表示されない場合は、インストーラーを
管理者として再実行し、Claude Desktop を再起動してください。
