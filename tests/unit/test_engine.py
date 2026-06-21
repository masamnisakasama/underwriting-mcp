"""ルールエンジンのユニットテスト（§12.4 precedence / forced-REFER）。"""
from __future__ import annotations

from underwriting_core.enums import Recommendation
from underwriting_core.facts import FactContext
from underwriting_core.rules.engine import ForcedReferGuards, evaluate_ruleset
from underwriting_core.rules.models import Ruleset

ELIGIBLE = Recommendation.ELIGIBLE_CANDIDATE
REFER = Recommendation.REFER
NOT_ELIGIBLE = Recommendation.NOT_ELIGIBLE_CANDIDATE


def _ruleset(*rules: dict) -> Ruleset:
    return Ruleset.model_validate(
        {"ruleset_version": "test-1", "product_code": "TEST", "rules": list(rules)}
    )


def _ctx(age: int) -> FactContext:
    return FactContext(values={"applicant": {"age": age}})


REFER_RULE = {
    "id": "R-REFER",
    "priority": 10,
    "description_ja": "refer",
    "when": {"gte": {"field": "applicant.age", "value": 60}},
    "result": "REFER",
    "reason_ja": "要査定",
    "required_information": ["medical.current_treatment"],
}
NOT_ELIGIBLE_RULE = {
    "id": "R-NG",
    "priority": 20,
    "description_ja": "ng",
    "when": {"gt": {"field": "applicant.age", "value": 70}},
    "result": "NOT_ELIGIBLE_CANDIDATE",
    "reason_ja": "上限超過",
}


def test_no_hit_no_guard_is_eligible() -> None:
    decision = evaluate_ruleset(_ruleset(REFER_RULE), _ctx(40))
    assert decision.recommendation is ELIGIBLE
    assert decision.rule_hits == []


def test_single_refer_hit() -> None:
    decision = evaluate_ruleset(_ruleset(REFER_RULE), _ctx(65))
    assert decision.recommendation is REFER
    assert [h.rule_id for h in decision.rule_hits] == ["R-REFER"]
    assert decision.required_information == ["medical.current_treatment"]


def test_precedence_not_eligible_beats_refer() -> None:
    # 75歳: REFER と NOT_ELIGIBLE の両方がヒット → NOT_ELIGIBLE が勝つ。
    decision = evaluate_ruleset(_ruleset(REFER_RULE, NOT_ELIGIBLE_RULE), _ctx(75))
    hit_ids = {h.rule_id for h in decision.rule_hits}
    assert hit_ids == {"R-REFER", "R-NG"}
    assert decision.recommendation is NOT_ELIGIBLE


def test_forced_refer_guard_overrides_eligible() -> None:
    guards = ForcedReferGuards(missing_required_document=True)
    decision = evaluate_ruleset(_ruleset(REFER_RULE), _ctx(40), guards)
    assert decision.recommendation is REFER
    assert decision.rule_hits == []
    assert decision.forced_refer_reasons == ["必須文書が不足しています"]


def test_forced_refer_does_not_downgrade_not_eligible() -> None:
    # 強制 REFER があっても NOT_ELIGIBLE は維持される（severity で max）。
    guards = ForcedReferGuards(low_confidence_important_field=True)
    decision = evaluate_ruleset(_ruleset(NOT_ELIGIBLE_RULE), _ctx(75), guards)
    assert decision.recommendation is NOT_ELIGIBLE
    assert decision.forced_refer_reasons == ["重要項目の抽出信頼度が基準未満です"]


def test_multiple_guards_listed() -> None:
    guards = ForcedReferGuards(
        missing_important_field=True, unresolved_contradiction=True
    )
    decision = evaluate_ruleset(_ruleset(), _ctx(40), guards)
    assert decision.recommendation is REFER
    assert decision.forced_refer_reasons == [
        "重要項目が不足しています",
        "未解決の帳票間矛盾があります",
    ]


def test_required_information_deduplicated() -> None:
    rule_a = {**REFER_RULE, "id": "A"}
    rule_b = {
        **REFER_RULE,
        "id": "B",
        "priority": 5,
        "required_information": ["medical.current_treatment", "medical.medications"],
    }
    decision = evaluate_ruleset(_ruleset(rule_a, rule_b), _ctx(65))
    assert decision.required_information == [
        "medical.current_treatment",
        "medical.medications",
    ]
