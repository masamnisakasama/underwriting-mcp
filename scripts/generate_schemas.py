"""Pydantic モデルから JSON Schema を生成する（§9 / §11）。

``schemas/*.schema.json`` を単一の真実（Pydantic モデル）から再生成する。
CI/テストでドリフト検出する（tests/unit/test_schemas.py）。

    python scripts/generate_schemas.py
"""
from __future__ import annotations

import json
from pathlib import Path

from underwriting_core.canonical import CanonicalFacts
from underwriting_core.result import UnderwritingResult

SCHEMAS_DIR = Path(__file__).resolve().parents[1] / "schemas"

TARGETS = {
    "canonical-facts.schema.json": CanonicalFacts,
    "underwriting-result.schema.json": UnderwritingResult,
}


def render(model: type) -> str:
    schema = model.model_json_schema()
    return json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> None:
    SCHEMAS_DIR.mkdir(parents=True, exist_ok=True)
    for filename, model in TARGETS.items():
        (SCHEMAS_DIR / filename).write_text(render(model), encoding="utf-8")
        print(f"wrote {filename}")


if __name__ == "__main__":
    main()
