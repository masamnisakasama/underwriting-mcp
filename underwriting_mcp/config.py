"""サーバ設定（環境変数, §16）。安全側の既定と fail-fast を持つ。"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]


class ConfigError(RuntimeError):
    """起動を止めるべき不正設定（production で no-auth 等）。"""


def _split_env(name: str, default: str) -> list[str]:
    raw = os.environ.get(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass(frozen=True)
class ServerConfig:
    environment: str = "demo"  # demo | staging | production
    auth_mode: str = "none"  # none | jwt | oauth | header
    app_mode: str = "mock"  # mock | aws
    host: str = "127.0.0.1"
    port: int = 8000
    public_base_url: str = "https://underwriting-mcp.local"
    enable_origin_check: bool = True
    allowed_origins: list[str] = field(default_factory=lambda: ["https://claude.ai"])
    allowed_hosts: list[str] = field(
        default_factory=lambda: ["127.0.0.1:*", "localhost:*"]
    )
    json_response: bool = True
    stateless_http: bool = True
    rulesets_dir: Path = _REPO_ROOT / "rulesets"
    samples_dir: Path = _REPO_ROOT / "samples"
    code_version: str | None = None
    jwt_secret: str | None = None
    jwt_issuer: str = "underwriting-demo"
    jwt_audience: str = "underwriting-mcp"

    def validate(self) -> ServerConfig:
        if self.auth_mode == "none" and self.environment != "demo":
            raise ConfigError(
                "AUTH_MODE=none は ENVIRONMENT=demo のときだけ許可されます（§16.1）。"
            )
        if self.app_mode not in ("mock", "aws"):
            raise ConfigError(f"未知の APP_MODE: {self.app_mode}")
        if self.auth_mode not in ("none", "jwt", "oauth", "header"):
            raise ConfigError(f"未知の AUTH_MODE: {self.auth_mode}")
        if self.auth_mode == "jwt" and not self.jwt_secret:
            raise ConfigError("AUTH_MODE=jwt では MCP_JWT_SECRET が必要です。")
        return self

    @classmethod
    def from_env(cls) -> ServerConfig:
        cfg = cls(
            environment=os.environ.get("ENVIRONMENT", "demo"),
            auth_mode=os.environ.get("AUTH_MODE", "none"),
            app_mode=os.environ.get("APP_MODE", "mock"),
            host=os.environ.get("MCP_HOST", "127.0.0.1"),
            port=int(os.environ.get("MCP_PORT", "8000")),
            public_base_url=os.environ.get(
                "PUBLIC_BASE_URL", "https://underwriting-mcp.local"
            ),
            enable_origin_check=os.environ.get("ENABLE_ORIGIN_CHECK", "1") != "0",
            allowed_origins=_split_env("ALLOWED_ORIGINS", "https://claude.ai"),
            allowed_hosts=_split_env("ALLOWED_HOSTS", "127.0.0.1:*,localhost:*"),
            code_version=os.environ.get("CODE_VERSION"),
            jwt_secret=os.environ.get("MCP_JWT_SECRET"),
            jwt_issuer=os.environ.get("MCP_JWT_ISSUER", "underwriting-demo"),
            jwt_audience=os.environ.get("MCP_JWT_AUDIENCE", "underwriting-mcp"),
        )
        return cfg.validate()
