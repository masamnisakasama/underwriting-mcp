$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Installer = Join-Path $Root "deploy\cowork\windows\install-demo.ps1"

if (!(Test-Path $Installer)) {
  throw "Missing installer: $Installer. Please unzip the whole bundle before running this script."
}

$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
$isAdmin = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (!$isAdmin) {
  throw "Please open PowerShell as Administrator, then run .\install-windows-demo.ps1 again."
}

& $Installer
