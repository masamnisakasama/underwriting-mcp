"""Underwriting decision core (AWS非依存・決定論ロジックの中核).

このパッケージは MCP サーバと各 Lambda の双方から import される共有ロジック。
AWS SDK には依存させない（テスト容易性と保守性のため）。
"""

__all__ = ["enums", "facts", "rules", "models"]
