"""決定論ルールエンジン（§12.4）。

責務:
- ルールセットを fact context に対して評価し、ヒットしたルールを集める。
- 判定の優先順位 NOT_ELIGIBLE > REFER > ELIGIBLE を適用する。
- 強制 REFER 条件（不足・低信頼・矛盾・LLM出力不正 等）を反映する。

LLM の自称判定は使わない。最終 recommendation はここ（決定論）でのみ決まる。
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ..enums import Recommendation
from ..facts import FactContext
from . import dsl
from .models import Rule, Ruleset


class RuleHit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_id: str
    result: Recommendation
    reason_ja: str = ""
    required_information: list[str] = Field(default_factory=list)


class ForcedReferGuards(BaseModel):
    """ルール結果に依らず最低でも REFER に倒す条件（§12.4）。

    各フラグはエンジンの外（抽出/検証段）で算出して渡す。エンジンは
    これらを「理由付きの強制 REFER」として反映するだけにし、責務を分離する。
    """

    model_config = ConfigDict(extra="forbid")

    missing_required_document: bool = False
    missing_important_field: bool = False
    low_confidence_important_field: bool = False
    unresolved_contradiction: bool = False
    llm_output_validation_failed: bool = False
    evidenceless_important_fact: bool = False

    def reasons(self) -> list[str]:
        mapping = [
            (self.missing_required_document, "必須文書が不足しています"),
            (self.missing_important_field, "重要項目が不足しています"),
            (self.low_confidence_important_field, "重要項目の抽出信頼度が基準未満です"),
            (self.unresolved_contradiction, "未解決の帳票間矛盾があります"),
            (self.llm_output_validation_failed, "構造化抽出の検証に失敗しました"),
            (self.evidenceless_important_fact, "根拠のない重要項目を判定に使用しました"),
        ]
        return [reason for triggered, reason in mapping if triggered]


class EngineDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommendation: Recommendation
    rule_hits: list[RuleHit]
    forced_refer_reasons: list[str]
    required_information: list[str]


def _to_hit(rule: Rule) -> RuleHit:
    return RuleHit(
        rule_id=rule.id,
        result=rule.result,
        reason_ja=rule.reason_ja,
        required_information=list(rule.required_information),
    )


def evaluate_ruleset(
    ruleset: Ruleset,
    ctx: FactContext,
    guards: ForcedReferGuards | None = None,
) -> EngineDecision:
    """ルールセットを評価して最終判定を返す。"""
    guards = guards or ForcedReferGuards()

    hits = [_to_hit(rule) for rule in ruleset.sorted_rules() if dsl.evaluate(rule.when, ctx)]
    forced_reasons = guards.reasons()

    candidates: list[Recommendation] = [hit.result for hit in hits]
    if forced_reasons:
        candidates.append(Recommendation.REFER)

    recommendation = (
        max(candidates, key=lambda r: r.severity)
        if candidates
        else Recommendation.ELIGIBLE_CANDIDATE
    )

    required: list[str] = []
    for hit in hits:
        for field in hit.required_information:
            if field not in required:
                required.append(field)

    return EngineDecision(
        recommendation=recommendation,
        rule_hits=hits,
        forced_refer_reasons=forced_reasons,
        required_information=required,
    )
