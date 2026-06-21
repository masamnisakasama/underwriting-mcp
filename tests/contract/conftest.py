"""contract テスト用に、実 uvicorn サーバをスレッド起動する fixture（§24.2）。

in-process の ASGI ではなく実 HTTP で起動し、Streamable HTTP のハンドシェイク・
Origin 検証まで含めて検証する。
"""
from __future__ import annotations

import socket
import threading
import time
from collections.abc import Iterator

import httpx
import pytest
import uvicorn

from underwriting_mcp.config import ServerConfig
from underwriting_mcp.server import create_app


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


class _Server:
    def __init__(self, config: ServerConfig) -> None:
        self.config = config
        self.base_url = f"http://{config.host}:{config.port}"
        self.mcp_url = f"{self.base_url}/mcp"
        app = create_app(config)
        self._uv = uvicorn.Server(
            uvicorn.Config(app, host=config.host, port=config.port, log_level="warning")
        )
        self._thread = threading.Thread(target=self._uv.run, daemon=True)

    def start(self) -> None:
        self._thread.start()
        deadline = time.time() + 10
        while time.time() < deadline:
            if self._uv.started:
                return
            time.sleep(0.05)
        raise RuntimeError("uvicorn did not start in time")

    def stop(self) -> None:
        self._uv.should_exit = True
        self._thread.join(timeout=10)


@pytest.fixture(scope="module")
def mcp_server() -> Iterator[_Server]:
    port = _free_port()
    config = ServerConfig(
        environment="demo",
        auth_mode="none",
        app_mode="mock",
        host="127.0.0.1",
        port=port,
        enable_origin_check=True,
        allowed_origins=["https://claude.ai"],
        allowed_hosts=["127.0.0.1:*", "localhost:*"],
    )
    server = _Server(config)
    server.start()
    try:
        yield server
    finally:
        server.stop()


@pytest.fixture()
def http(mcp_server: _Server) -> Iterator[httpx.Client]:
    with httpx.Client(base_url=mcp_server.base_url, timeout=10) as client:
        yield client
