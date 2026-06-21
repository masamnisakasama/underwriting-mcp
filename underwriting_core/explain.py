"""保存済み結果のみに基づく決定論的な説明（§8.2 explain）。

新しいルールを生成せず、根拠のない医学的判断もしない。保存済みの rule hits・
forced REFER 理由・矛盾・不足情報だけを根拠として回答を組み立て、必ず
evidence_ids と rule_ids を添える。説明できる材料が無ければ「判断できない」と返す。
"""
from __future__ import annotations

from .enums import Recommendation
from .result import UnderwritingResult


class Explanation:
    def __init__(
        self,
        answerable: bool,
        answer_ja: str,
        evidence_ids: list[str],
        rule_ids: list[str],
    ) -> None:
        self.answerable = answerable
        self.answer_ja = answer_ja
        self.evidence_ids = evidence_ids
        self.rule_ids = rule_ids


def explain(result: UnderwritingResult, question: str) -> Explanation:
    if not question.strip():
        return Explanation(False, "質問が空です。", [], [])

    rule_ids = [hit.rule_id for hit in result.rule_hits]
    evidence_ids: list[str] = []
    for hit in result.rule_hits:
        evidence_ids.extend(eid for eid in hit.evidence_ids if eid not in evidence_ids)
    for con in result.contradictions:
        evidence_ids.extend(eid for eid in con.evidence_ids if eid not in evidence_ids)

    reasons: list[str] = [hit.reason_ja for hit in result.rule_hits if hit.reason_ja]
    reasons += result.forced_refer_reasons
    if result.missing_information:
        reasons += [f"不足: {m.reason_ja}" for m in result.missing_information]

    label = result.recommendation_label_ja
    if reasons:
        body = "／".join(reasons)
        return Explanation(True, f"判定は「{label}」です。根拠: {body}。", evidence_ids, rule_ids)

    if result.recommendation is Recommendation.ELIGIBLE_CANDIDATE:
        return Explanation(
            True,
            f"判定は「{label}」です。デモ基準に該当する事象・不足・矛盾はありません。",
            evidence_ids,
            rule_ids,
        )

    return Explanation(False, "保存済み情報では判断できません。", [], [])
