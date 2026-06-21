"""canonical facts + ルールエンジン結果 → 最終結果の組み立て（§9 / §9.1 / §12.4）。

純粋ロジック（IO なし）。強制 REFER ガードの算出、サーバー側 confidence 算出、
決定論的な日本語サマリ生成、Result Schema への組み立てを担う。

confidence は LLM の自称値ではなく、Textract confidence・schema validation・
evidence availability からサーバー側で算出する（§9.1）。
"""
from __future__ import annotations

from .canonical import (
    CONFIDENCE_FLOOR,
    IMPORTANT_FIELDS,
    CanonicalFacts,
)
from .agent import assess_agent_findings
from .enums import FactStatus, Recommendation, Severity
from .result import (
    AgentFindingOut,
    ContradictionOut,
    EvidenceOut,
    MissingInformation,
    RuleHitOut,
    UnderwritingResult,
)
from .rules import dsl
from .rules.engine import EngineDecision, ForcedReferGuards, evaluate_ruleset
from .rules.models import Ruleset


def derive_guards(facts: CanonicalFacts) -> ForcedReferGuards:
    """canonical facts から強制 REFER ガード（§12.4）を算出する。"""
    expected = set(facts.expected_documents)
    present = set(facts.present_documents)
    missing_required_document = bool(expected - present)

    missing_important_field = False
    low_confidence_important_field = False
    evidenceless_important_fact = False
    for field in IMPORTANT_FIELDS:
        meta = facts.field_meta.get(field)
        if meta is None:
            continue
        if meta.status in (FactStatus.MISSING, FactStatus.AMBIGUOUS, FactStatus.CONTRADICTED):
            missing_important_field = True
        if meta.status is FactStatus.PRESENT:
            if meta.confidence is not None and meta.confidence < CONFIDENCE_FLOOR:
                low_confidence_important_field = True
            if not meta.evidence_ids:
                evidenceless_important_fact = True

    return ForcedReferGuards(
        missing_required_document=missing_required_document,
        missing_important_field=missing_important_field,
        low_confidence_important_field=low_confidence_important_field,
        unresolved_contradiction=bool(facts.contradictions),
        llm_output_validation_failed=facts.extraction_validation_failed,
        evidenceless_important_fact=evidenceless_important_fact,
    )


def compute_confidence(facts: CanonicalFacts) -> float:
    """重要項目の抽出 confidence を集約（§9.1）。

    - 検証失敗時は下限まで下げる。
    - PRESENT な重要項目の最小 confidence を基準にする。
    - evidence の無い重要項目があれば減点する。
    confidence は参考値であり判定 precedence には使わない（§9.1）。
    """
    if facts.extraction_validation_failed:
        return 0.5

    confidences: list[float] = []
    penalty = 0.0
    for field in IMPORTANT_FIELDS:
        meta = facts.field_meta.get(field)
        if meta is None or meta.status is not FactStatus.PRESENT:
            continue
        if meta.confidence is not None:
            confidences.append(meta.confidence)
        if not meta.evidence_ids:
            penalty += 0.1

    base = min(confidences) if confidences else 0.7
    return round(max(0.0, min(1.0, base - penalty)), 4)


def build_summary(decision: EngineDecision, facts: CanonicalFacts) -> str:
    """決定論的な日本語サマリ（mock）。Bedrock narrative は AWS 段階で置換する。"""
    label = decision.recommendation.label_ja
    parts: list[str] = []
    if decision.rule_hits:
        parts.append("・".join(hit.reason_ja for hit in decision.rule_hits if hit.reason_ja))
    if decision.forced_refer_reasons:
        parts.append("・".join(decision.forced_refer_reasons))
    if facts.contradictions:
        parts.append(facts.contradictions[0].description_ja)
    detail = "。".join(p for p in parts if p)
    if detail:
        return f"判定は「{label}」です。{detail}。"
    return f"判定は「{label}」です。デモ基準に該当する事象はありません。"


def _agent_enabled(ruleset: Ruleset) -> bool:
    return ruleset.ruleset_version >= "demo-medical-2026-02"


def _compose_recommendation(
    recommendation: Recommendation,
    agent_findings: list[AgentFindingOut],
) -> Recommendation:
    candidates = [recommendation]
    candidates.extend(f.severity_suggestion for f in agent_findings)
    return max(candidates, key=lambda r: r.severity)


def _missing_information(
    decision: EngineDecision,
    facts: CanonicalFacts,
    agent_findings: list[AgentFindingOut],
) -> list[MissingInformation]:
    missing: list[MissingInformation] = [
        MissingInformation(field=m.field, reason_ja=m.reason_ja, severity=m.severity)
        for m in facts.missing_information
    ]
    seen = {m.field for m in missing}
    for field in decision.required_information:
        if field in seen:
            continue
        missing.append(
            MissingInformation(
                field=field,
                reason_ja=f"{field} の追加確認が必要です",
                severity=(
                    Severity.HIGH
                    if decision.recommendation.severity >= Recommendation.REFER_MEDICAL_REVIEW.severity
                    else Severity.MEDIUM
                ),
            )
        )
        seen.add(field)
    for finding in agent_findings:
        for field in finding.recommended_follow_up:
            if field in seen:
                continue
            missing.append(
                MissingInformation(
                    field=field,
                    reason_ja=f"{field} の追加確認が必要です",
                    severity=Severity.MEDIUM,
                )
            )
            seen.add(field)
    return missing


def _rule_hit_evidence_ids(rule_when: dict, facts: CanonicalFacts) -> list[str]:
    """ルール条件が参照する項目の evidence_ids を集約する。"""
    ids: list[str] = []
    for field in dsl.referenced_fields(rule_when):
        # contradictions.<key> はそのキーの contradiction evidence を引く。
        if field.startswith("contradictions."):
            key = field.split(".", 1)[1]
            for con in facts.contradictions:
                if con.key == key:
                    ids.extend(eid for eid in con.evidence_ids if eid not in ids)
            continue
        for eid in facts.evidence_ids_for(field):
            if eid not in ids:
                ids.append(eid)
    return ids


def assemble_result(
    *,
    facts: CanonicalFacts,
    ruleset: Ruleset,
    case_id: str,
    job_id: str,
    created_at: str,
    completed_at: str,
    model_id: str = "mock",
    document_hashes: dict[str, str] | None = None,
    code_version: str | None = None,
    workflow_execution_arn: str | None = None,
) -> UnderwritingResult:
    """canonical facts を決定論評価し、最終結果へ組み立てる。"""
    ctx = facts.to_fact_context()
    guards = derive_guards(facts)
    decision: EngineDecision = evaluate_ruleset(ruleset, ctx, guards)
    agent_findings = assess_agent_findings(facts) if _agent_enabled(ruleset) else []
    recommendation = _compose_recommendation(decision.recommendation, agent_findings)

    # ルール条件で参照したフィールドから evidence を引いて hit に付与する。
    rule_when_by_id = {rule.id: rule.when for rule in ruleset.rules}
    rule_hits = [
        RuleHitOut(
            rule_id=hit.rule_id,
            result=hit.result,
            reason_ja=hit.reason_ja,
            evidence_ids=_rule_hit_evidence_ids(rule_when_by_id.get(hit.rule_id, {}), facts),
        )
        for hit in decision.rule_hits
    ]

    human_review_required = (
        recommendation is not Recommendation.ELIGIBLE_CANDIDATE
        or bool(decision.forced_refer_reasons)
        or bool(agent_findings)
    )

    return UnderwritingResult(
        case_id=case_id,
        job_id=job_id,
        recommendation=recommendation,
        recommendation_label_ja=recommendation.label_ja,
        human_review_required=human_review_required,
        confidence=compute_confidence(facts),
        summary_ja=build_summary(
            decision.model_copy(update={"recommendation": recommendation}), facts
        ),
        applicant_facts=dict(facts.applicant),
        health_facts=dict(facts.health) | {
            "current_treatment": facts.medical.get("current_treatment"),
            "current_medications": facts.medical.get("current_medications", []),
            "medications": facts.medical.get("medications"),
            "disclosure": facts.medical.get("disclosure"),
        },
        missing_information=_missing_information(decision, facts, agent_findings),
        contradictions=[
            ContradictionOut(
                contradiction_id=c.contradiction_id,
                description_ja=c.description_ja,
                evidence_ids=list(c.evidence_ids),
            )
            for c in facts.contradictions
        ],
        forced_refer_reasons=decision.forced_refer_reasons,
        rule_hits=rule_hits,
        agent_findings=agent_findings,
        evidence=[EvidenceOut(**e.model_dump()) for e in facts.evidence],
        ruleset_version=ruleset.ruleset_version,
        model_id=model_id,
        document_hashes=document_hashes or {},
        code_version=code_version,
        workflow_execution_arn=workflow_execution_arn,
        created_at=created_at,
        completed_at=completed_at,
    )
