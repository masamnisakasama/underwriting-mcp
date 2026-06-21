#!/usr/bin/env bash
set -euo pipefail

PLUGIN_DST="/Library/Application Support/Claude/org-plugins/underwriting-review"

rm -rf "${PLUGIN_DST}"
echo "Removed Underwriting Review plugin. Remove the mobileconfig profile from System Settings if needed."
