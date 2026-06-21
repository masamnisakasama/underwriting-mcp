"""ローカル mock end-to-end（§27-5）。

6 つの MCP tool 操作を service 経由で通し、Case A/B/C が期待判定になることと、
explain / simulate / 冪等性が仕様どおり動くことを実 fixture で検証する。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from underwriting_app.factory import build_mock_service
from underwriting_app.models import (
    CreateCaseInput,
    ExplainInput,
    GetReviewInput,
    ScenarioChange,
    SimulateInput,
    StartReviewInput,
)
from underwriting_core.result import UnderwritingResult

REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLES = REPO_ROOT / "samples"
RULESET_VERSION = "demo-medical-2026-01"


@pytest.fixture()
def service():
    return build_mock_service(code_version="test")


def _run(service, case_id: str) -> UnderwritingResult:
    start = service.start_underwriting_review(
        StartReviewInput(case_id=case_id, ruleset_version=RULESET_VERSION)
    )
    review = service.get_underwriting_review(GetReviewInput(job_id=start.job_id))
    assert isinstance(review, UnderwritingResult)
    return review


@pytest.mark.parametrize("case_dir", ["case-a", "case-b", "case-c"])
def test_demo_cases_match_expected(service, case_dir: str) -> None:
    expected = json.loads((SAMPLES / case_dir / "expected-result.json").read_text("utf-8"))
    case_id = json.loads((SAMPLES / case_dir / "case.json").read_text("utf-8"))["case_id"]

    result = _run(service, case_id)

    assert result.recommendation.value == expected["recommendation"]
    assert result.human_review_required == expected["human_review_required"]
    assert sorted(h.rule_id for h in result.rule_hits) == sorted(expected["rule_hit_ids"])
    assert sorted(result.forced_refer_reasons) == sorted(expected["forced_refer_reasons"])


def test_list_demo_cases(service) -> None:
    cases = service.list_demo_cases()
    names = {c.case_name for c in cases}
    assert {"case-a", "case-b", "case-c"} <= names
    case_b = next(c for c in cases if c.case_name == "case-b")
    assert case_b.expected_recommendation == "REFER"


def test_evidence_is_page_traceable(service) -> None:
    result = _run(service, "uw_demo_case_b")
    bp_hit = next(h for h in result.rule_hits if h.rule_id == "DEMO-UW-017")
    assert "ev_028" in bp_hit.evidence_ids
    ev = next(e for e in result.evidence if e.evidence_id == "ev_028")
    assert ev.page == 1
    assert ev.document_type.value == "HEALTH_CHECK"


def test_idempotent_start(service) -> None:
    a = service.start_underwriting_review(
        StartReviewInput(case_id="uw_demo_case_a", ruleset_version=RULESET_VERSION)
    )
    b = service.start_underwriting_review(
        StartReviewInput(case_id="uw_demo_case_a", ruleset_version=RULESET_VERSION)
    )
    assert a.job_id == b.job_id


def test_explain_grounded(service) -> None:
    start = service.start_underwriting_review(
        StartReviewInput(case_id="uw_demo_case_b", ruleset_version=RULESET_VERSION)
    )
    exp = service.explain_underwriting_review(
        ExplainInput(job_id=start.job_id, question="なぜ要査定なのですか")
    )
    assert exp.answerable is True
    assert "要査定" in exp.answer_ja
    assert "DEMO-UW-017" in exp.rule_ids
    assert exp.evidence_ids  # 根拠 id が必ず付く


def test_simulate_changes_outcome(service) -> None:
    # Case B を健康側へ what-if すると REFER が解消する方向に変わる。
    start = service.start_underwriting_review(
        StartReviewInput(case_id="uw_demo_case_b", ruleset_version=RULESET_VERSION)
    )
    sim = service.simulate_underwriting_change(
        SimulateInput(
            job_id=start.job_id,
            changes=[
                ScenarioChange(field="health.blood_pressure.systolic", value=128),
                ScenarioChange(field="health.blood_pressure.diastolic", value=78),
                ScenarioChange(field="medical.current_treatment", value=False),
            ],
        )
    )
    assert sim.before.recommendation == "REFER"
    # 高血圧+治療不明ルールは消えるが、矛盾ルール/矛盾ガードは残るため依然 REFER。
    assert "DEMO-UW-017" in sim.changed_rule_hit_ids
    # 元の結果は変更されない。
    review = service.get_underwriting_review(GetReviewInput(job_id=start.job_id))
    assert isinstance(review, UnderwritingResult)
    assert review.recommendation.value == "REFER"


def test_real_upload_not_available_in_mock(service) -> None:
    from underwriting_app.errors import ErrorCode, ToolError
    from underwriting_core.enums import DocumentType

    created = service.create_underwriting_case(
        CreateCaseInput(
            case_name="adhoc",
            product_code="DEMO_MEDICAL_01",
            applicant_age=45,
            expected_documents=[DocumentType.APPLICATION_FORM],
        )
    )
    with pytest.raises(ToolError) as ei:
        service.start_underwriting_review(
            StartReviewInput(case_id=created.case_id, ruleset_version=RULESET_VERSION)
        )
    assert ei.value.code is ErrorCode.NOT_AVAILABLE_IN_MODE
    # ジョブは FAILED として記録される（偽の成功にしない, §31）。
    from underwriting_app.models import GetReviewInput as _G  # local alias

    with pytest.raises(ToolError):
        service.get_underwriting_review(_G(job_id="job_does_not_exist"))


def test_unknown_failed_job_error_code_falls_back(service) -> None:
    from underwriting_app.errors import ErrorCode, ToolError
    from underwriting_app.models import JobStatus

    start = service.start_underwriting_review(
        StartReviewInput(case_id="uw_demo_case_a", ruleset_version=RULESET_VERSION)
    )
    job = service._jobs.get_job(start.job_id)  # noqa: SLF001 - integration fault injection.
    assert job is not None
    job.status = JobStatus.FAILED
    job.error_code = "Lambda.ServiceException"
    service._jobs.put_job(job)  # noqa: SLF001

    with pytest.raises(ToolError) as exc:
        service.get_underwriting_review(GetReviewInput(job_id=start.job_id))
    assert exc.value.code is ErrorCode.INTERNAL_ERROR
