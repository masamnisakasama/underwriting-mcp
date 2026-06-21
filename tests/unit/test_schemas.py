"""JSON Schema のドリフト検出 + tool I/O モデルの round-trip（§24.1）。

``schemas/*.schema.json`` が Pydantic モデルと一致していることを保証する。
ずれた場合は ``python scripts/generate_schemas.py`` で再生成する。
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from underwriting_core.canonical import CanonicalFacts
from underwriting_core.result import UnderwritingResult

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMAS_DIR = REPO_ROOT / "schemas"

# scripts/generate_schemas.py の render を import（パッケージ外なので spec から読み込む）。
_spec = importlib.util.spec_from_file_location(
    "generate_schemas", REPO_ROOT / "scripts" / "generate_schemas.py"
)
assert _spec and _spec.loader
_gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_gen)


def test_result_schema_in_sync() -> None:
    committed = (SCHEMAS_DIR / "underwriting-result.schema.json").read_text("utf-8")
    assert committed == _gen.render(UnderwritingResult), (
        "underwriting-result.schema.json が古い。scripts/generate_schemas.py を実行。"
    )


def test_canonical_schema_in_sync() -> None:
    committed = (SCHEMAS_DIR / "canonical-facts.schema.json").read_text("utf-8")
    assert committed == _gen.render(CanonicalFacts), (
        "canonical-facts.schema.json が古い。scripts/generate_schemas.py を実行。"
    )


def test_result_schema_is_valid_json() -> None:
    schema = json.loads((SCHEMAS_DIR / "underwriting-result.schema.json").read_text("utf-8"))
    assert schema["title"] == "UnderwritingResult"
    assert "recommendation" in schema["properties"]
