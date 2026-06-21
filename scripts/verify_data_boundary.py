#!/usr/bin/env python3
"""Static checks for V2 data-boundary packaging assumptions."""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    errors: list[str] = []
    plugin = ROOT / "plugin" / "underwriting-review"
    if any(path.name == ".mcp.json" for path in plugin.rglob("*")):
        errors.append("Plugin must not contain .mcp.json; managedMcpServers is authoritative.")

    zip_path = ROOT / "dist" / "underwriting-review-plugin.zip"
    if zip_path.is_file():
        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
            if any(name.endswith(".mcp.json") for name in names):
                errors.append("Plugin zip contains .mcp.json.")
            for name in names:
                if name.endswith((".md", ".json", ".py")):
                    data = zf.read(name).decode("utf-8", errors="ignore")
                    if "REPLACE_DEMO_MCP_TOKEN" in data or "MCP_BEARER_TOKEN=" in data:
                        errors.append(f"Potential token placeholder leaked into zip: {name}")

    required = [
        ROOT / "docs" / "DATA_BOUNDARY.md",
        ROOT / "deploy" / "cowork" / "templates" / "managed-mcp-servers.json.template",
        ROOT / "deploy" / "cowork" / "templates" / "cowork-3p-demo.json.template",
    ]
    for path in required:
        if not path.is_file():
            errors.append(f"Missing required artifact: {path.relative_to(ROOT)}")

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("Data-boundary packaging checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
