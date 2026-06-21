$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..\..")
$PluginSrc = Join-Path $Root "plugin\underwriting-review"
$PluginDst = "C:\Program Files\Claude\org-plugins\underwriting-review"
$RegPath = Join-Path $Root "deploy\cowork\generated\cowork-3p-demo.reg"
$Workspace = Join-Path $HOME "Documents\UnderwritingDemo"

if (!(Test-Path $RegPath)) {
  throw "Missing generated reg file: $RegPath"
}

New-Item -ItemType Directory -Force -Path (Split-Path $PluginDst) | Out-Null
if (Test-Path $PluginDst) {
  Remove-Item -Recurse -Force $PluginDst
}
Copy-Item -Recurse $PluginSrc $PluginDst
New-Item -ItemType Directory -Force -Path $Workspace | Out-Null
reg import $RegPath

Write-Host "Installed Underwriting Review plugin and Cowork 3P registry settings."
Write-Host "Restart Claude Desktop and sign in with AWS."
