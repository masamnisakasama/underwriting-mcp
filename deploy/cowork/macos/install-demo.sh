#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
PLUGIN_SRC="${ROOT_DIR}/plugin/underwriting-review"
PLUGIN_DST="/Library/Application Support/Claude/org-plugins/underwriting-review"
CONFIG="${ROOT_DIR}/deploy/cowork/generated/cowork-3p-demo.mobileconfig"
WORKSPACE="${HOME}/Documents/UnderwritingDemo"

if [[ ! -f "${CONFIG}" ]]; then
  echo "Missing generated mobileconfig: ${CONFIG}" >&2
  exit 2
fi

mkdir -p "$(dirname "${PLUGIN_DST}")"
rm -rf "${PLUGIN_DST}"
cp -R "${PLUGIN_SRC}" "${PLUGIN_DST}"
mkdir -p "${WORKSPACE}"
profiles install -type configuration -path "${CONFIG}"

echo "Installed Underwriting Review plugin and Cowork 3P profile."
echo "Restart Claude Desktop and sign in with AWS."
