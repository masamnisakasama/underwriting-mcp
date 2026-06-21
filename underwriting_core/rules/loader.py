"""ルールセットの読み込み（YAML -> Pydantic 検証）。"""
from __future__ import annotations

from pathlib import Path

import yaml

from .models import Ruleset


class RulesetNotFoundError(FileNotFoundError):
    """エラーコード RULESET_NOT_FOUND に対応。"""


def load_ruleset_from_yaml(path: str | Path) -> Ruleset:
    p = Path(path)
    if not p.is_file():
        raise RulesetNotFoundError(f"ruleset が見つかりません: {p}")
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return Ruleset.model_validate(data)


def load_ruleset(rulesets_dir: str | Path, ruleset_version: str) -> Ruleset:
    """``<rulesets_dir>/<version>/rules.yaml`` を読み込む。"""
    path = Path(rulesets_dir) / ruleset_version / "rules.yaml"
    if not path.is_file():
        raise RulesetNotFoundError(f"ruleset version が見つかりません: {ruleset_version}")
    return load_ruleset_from_yaml(path)
