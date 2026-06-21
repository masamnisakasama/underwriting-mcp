$ErrorActionPreference = "Stop"

$PluginDst = "C:\Program Files\Claude\org-plugins\underwriting-review"
if (Test-Path $PluginDst) {
  Remove-Item -Recurse -Force $PluginDst
}
Write-Host "Removed Underwriting Review plugin. Remove registry policy values if needed."
