"""ルールセット読み込み + 実データに対する end-to-end 評価。

実在する demo-medical-2026-01 ルールセットを読み込み、3 ケース
（適格候補 / 要査定 / 不可候補）が仕様どおり判定されることを確認する。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from underwriting_core.enums import Recommendation
from underwriting_core.facts import FactContext
from underwriting_core.rules.engine import evaluate_ruleset
from underwriting_core.rules.loader import (
    RulesetNotFoundError,
    load_ruleset,
    load_ruleset_from_yaml,
)

RULESETS_DIR = Path(__file__).resolve().parents[2] / "rulesets"
VERSION = "demo-medical-2026-01"


def test_load_real_ruleset() -> None:
    ruleset = load_ruleset(RULESETS_DIR, VERSION)
    assert ruleset.ruleset_version == VERSION
    assert ruleset.product_code == "DEMO_MEDICAL_01"
    # priority 降順で整列されていること。
    priorities = [r.priority for r in ruleset.sorted_rules()]
    assert priorities == sorted(priorities, reverse=True)


def test_missing_ruleset_raises() -> None:
    with pytest.raises(RulesetNotFoundError):
        load_ruleset(RULESETS_DIR, "does-not-exist")
    with pytest.raises(RulesetNotFoundError):
        load_ruleset_from_yaml(RULESETS_DIR / "nope.yaml")


def _decide(values: dict) -> Recommendation:
    ruleset = load_ruleset(RULESETS_DIR, VERSION)
    return evaluate_ruleset(ruleset, FactContext(values=values)).recommendation


def test_case_a_eligible() -> None:
    # 健康な40歳: どのルールにもヒットしない → 適格候補。
    values = {
        "applicant": {"age": 40},
        "health": {"blood_pressure": {"systolic": 120, "diastolic": 78}, "hba1c": 5.4},
        "medical": {"current_treatment": False},
        "contradictions": {},
    }
    assert _decide(values) is Recommendation.ELIGIBLE_CANDIDATE


def test_case_b_refer_high_bp_missing_treatment() -> None:
    # 高血圧 + 治療状況不明 + 矛盾 → 要査定。
    values = {
        "applicant": {"age": 52},
        "health": {"blood_pressure": {"systolic": 165, "diastolic": 105}, "hba1c": 5.8},
        "medical": {},
        "contradictions": {"health_exam": {"id": "con_001"}},
    }
    assert _decide(values) is Recommendation.REFER


def test_case_c_not_eligible_over_age() -> None:
    # 75歳: 上限超過 → 不可候補（REFER条件があっても precedence で勝つ）。
    values = {
        "applicant": {"age": 75},
        "health": {"blood_pressure": {"systolic": 170, "diastolic": 110}, "hba1c": 7.0},
        "medical": {},
        "contradictions": {"health_exam": {"id": "con_002"}},
    }
    assert _decide(values) is Recommendation.NOT_ELIGIBLE_CANDIDATE
