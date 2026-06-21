"""ローカル起動: ``python -m underwriting_mcp``（make dev-mcp, §22.3）。

http://127.0.0.1:8000/mcp で Streamable HTTP MCP を提供する。
"""
from __future__ import annotations

import uvicorn

from .config import ServerConfig
from .server import create_app


def main() -> None:
    config = ServerConfig.from_env()
    app = create_app(config)
    print(
        f"[underwriting-mcp] env={config.environment} mode={config.app_mode} "
        f"auth={config.auth_mode} -> http://{config.host}:{config.port}/mcp"
    )
    uvicorn.run(app, host=config.host, port=config.port, log_level="info")


if __name__ == "__main__":
    main()
