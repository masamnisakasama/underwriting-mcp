"""canonical facts → 結果組み立て（confidence / guards / evidence 紐付け）のテスト。"""
from __future__ import annotations

from pathlib import Path

from underwriting_core.assembly import (
    assemble_result,
    compute_confidence,
    derive_guards,
)
from underwriting_core.canonical import (
    CanonicalFacts,
    ContradictionItem,
    Evidence,
    FactMeta,
    MissingInfoItem,
)
from underwriting_core.enums import DocumentType, FactStatus, Recommendation, Severity
from underwriting_core.rules.loader import load_ruleset

RULESETS_DIR = Path(__file__).resolve().parents[2] / "rulesets"
RULESET = load_ruleset(RULESETS_DIR, "demo-medical-2026-01")

ALL_DOCS = [
    DocumentType.APPLICATION_FORM,
    DocumentType.MEDICAL_DISCLOSURE,
    DocumentType.HEALTH_CHECK,
]


def _meta_present(conf: float, evidence_ids: list[str]) -> FactMeta:
    return FactMeta(status=FactStatus.PRESENT, confidence=conf, evidence_ids=evidence_ids)


def _assemble(facts: CanonicalFacts):
    return assemble_result(
        facts=facts,
        ruleset=RULESET,
        case_id="uw_test",
        job_id="job_test",
        created_at="2026-06-20T10:00:00Z",
        completed_at="2026-06-20T10:00:10Z",
    )


def _case_a() -> CanonicalFacts:
    return CanonicalFacts(
        applicant={"age": 40, "product_code": "DEMO_MEDICAL_01"},
        health={"blood_pressure": {"systolic": 120, "diastolic": 78}, "hba1c": 5.4},
        medical={"current_treatment": False, "current_medications": []},
        expected_documents=ALL_DOCS,
        present_documents=ALL_DOCS,
        field_meta={
            "applicant.age": _meta_present(0.99, ["ev_age"]),
            "health.blood_pressure.systolic": _meta_present(0.98, ["ev_bp"]),
            "health.blood_pressure.diastolic": _meta_present(0.98, ["ev_bp"]),
            "health.hba1c": _meta_present(0.97, ["ev_hba1c"]),
            "medical.current_treatment": _meta_present(0.95, ["ev_treat"]),
        },
        evidence=[
            Evidence(
                evidence_id="ev_bp",
                document_id="doc_health",
                document_type=DocumentType.HEALTH_CHECK,
                file_name="health_check.pdf",
                page=1,
                field="blood_pressure",
                text="120 / 78 mmHg",
                confidence=0.98,
            )
        ],
    )


def test_case_a_eligible_no_human_review() -> None:
    result = _assemble(_case_a())
    assert result.recommendation is Recommendation.ELIGIBLE_CANDIDATE
    assert result.recommendation_label_ja == "引受候補"
    assert result.human_review_required is False
    assert result.rule_hits == []
    assert result.forced_refer_reasons == []
    assert result.confidence >= 0.9


def test_case_b_refer_with_evidence_and_guards() -> None:
    facts = CanonicalFacts(
        applicant={"age": 52, "product_code": "DEMO_MEDICAL_01"},
        health={"blood_pressure": {"systolic": 165, "diastolic": 105}, "hba1c": 5.8},
        medical={"current_medications": []},  # current_treatment は欠落
        expected_documents=ALL_DOCS,
        present_documents=ALL_DOCS,
        field_meta={
            "applicant.age": _meta_present(0.99, ["ev_age"]),
            "health.blood_pressure.systolic": _meta_present(0.98, ["ev_028"]),
            "health.blood_pressure.diastolic": _meta_present(0.98, ["ev_028"]),
            "medical.current_treatment": FactMeta(status=FactStatus.MISSING),
        },
        contradictions=[
            ContradictionItem(
                contradiction_id="con_001",
                key="health_exam",
                description_ja="告知書は異常なしだが健診は要受診",
                evidence_ids=["ev_014", "ev_028"],
            )
        ],
        missing_information=[
            MissingInfoItem(
                field="medical.current_treatment",
                reason_ja="治療状況が未記載",
                severity=Severity.HIGH,
            )
        ],
        evidence=[
            Evidence(
                evidence_id="ev_028",
                document_id="doc_health",
                document_type=DocumentType.HEALTH_CHECK,
                file_name="health_check.pdf",
                page=1,
                field="blood_pressure",
                text="165 / 105 mmHg",
                confidence=0.98,
            )
        ],
    )
    result = _assemble(facts)
    assert result.recommendation is Recommendation.REFER
    assert result.human_review_required is True
    hit_ids = {h.rule_id for h in result.rule_hits}
    assert {"DEMO-UW-017", "DEMO-UW-030"} <= hit_ids
    # 高血圧ルールは血圧 evidence を根拠として引く。
    bp_hit = next(h for h in result.rule_hits if h.rule_id == "DEMO-UW-017")
    assert "ev_028" in bp_hit.evidence_ids
    # 矛盾ルールは contradiction evidence を引く。
    con_hit = next(h for h in result.rule_hits if h.rule_id == "DEMO-UW-030")
    assert "ev_014" in con_hit.evidence_ids
    assert "重要項目が不足しています" in result.forced_refer_reasons
    assert "未解決の帳票間矛盾があります" in result.forced_refer_reasons
    assert result.health_facts["current_treatment"] is None


def test_case_c_not_eligible_precedence() -> None:
    facts = CanonicalFacts(
        applicant={"age": 75, "product_code": "DEMO_MEDICAL_01"},
        health={"blood_pressure": {"systolic": 170, "diastolic": 110}, "hba1c": 7.2},
        medical={},
        expected_documents=ALL_DOCS,
        present_documents=ALL_DOCS,
        contradictions=[
            ContradictionItem(
                contradiction_id="con_002",
                key="health_exam",
                description_ja="不整合",
                evidence_ids=["ev_x"],
            )
        ],
    )
    result = _assemble(facts)
    # REFER 条件があっても precedence で NOT_ELIGIBLE が勝つ。
    assert result.recommendation is Recommendation.NOT_ELIGIBLE_CANDIDATE


def test_missing_required_document_forces_refer() -> None:
    facts = _case_a()
    facts.present_documents = [DocumentType.APPLICATION_FORM]  # 2 件不足
    guards = derive_guards(facts)
    assert guards.missing_required_document is True
    result = _assemble(facts)
    assert result.recommendation is Recommendation.REFER
    assert "必須文書が不足しています" in result.forced_refer_reasons


def test_confidence_validation_failed_is_low() -> None:
    facts = _case_a()
    facts.extraction_validation_failed = True
    assert compute_confidence(facts) == 0.5
    result = _assemble(facts)
    assert result.recommendation is Recommendation.REFER
    assert "構造化抽出の検証に失敗しました" in result.forced_refer_reasons


def test_low_confidence_field_forces_refer() -> None:
    facts = _case_a()
    facts.field_meta["health.hba1c"] = _meta_present(0.6, ["ev_hba1c"])
    guards = derive_guards(facts)
    assert guards.low_confidence_important_field is True
    result = _assemble(facts)
    assert result.recommendation is Recommendation.REFER
