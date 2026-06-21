from __future__ import annotations

from pathlib import Path

import pytest

from underwriting_app.errors import ErrorCode, ToolError
from underwriting_app.factory import build_mock_service
from underwriting_app.models import (
    GetReviewInput,
    ScenarioChange,
    SimulateInput,
    StartReviewInput,
)
from underwriting_core.result import UnderwritingResult

RULESET_VERSION = "demo-medical-2026-02"


@pytest.fixture()
def service():
    return build_mock_service(code_version="test-v2")


def _run_case_a(service) -> tuple[str, UnderwritingResult]:
    start = service.start_underwriting_review(
        StartReviewInput(case_id="uw_demo_case_a", ruleset_version=RULESET_VERSION)
    )
    review = service.get_underwriting_review(GetReviewInput(job_id=start.job_id))
    assert isinstance(review, UnderwritingResult)
    return start.job_id, review


def _run_case(service, case_id: str) -> tuple[str, UnderwritingResult]:
    start = service.start_underwriting_review(
        StartReviewInput(case_id=case_id, ruleset_version=RULESET_VERSION)
    )
    review = service.get_underwriting_review(GetReviewInput(job_id=start.job_id))
    assert isinstance(review, UnderwritingResult)
    return start.job_id, review


def test_case_a_is_eligible_under_v2(service) -> None:
    _, result = _run_case_a(service)
    assert result.ruleset_version == RULESET_VERSION
    assert result.recommendation.value == "ELIGIBLE_CANDIDATE"
    assert result.human_review_required is False
    assert result.rule_hits == []
    assert result.agent_findings == []


def test_case_d_ambiguous_free_text_moves_to_info_request(service) -> None:
    _, result = _run_case(service, "uw_demo_case_d")
    assert result.recommendation.value == "REFER_INFO_REQUEST"
    assert result.human_review_required is True
    assert result.rule_hits == []
    assert [f.finding_id for f in result.agent_findings] == ["AGENT-FREE-TEXT-001"]
    assert "ev_d_disclosure_free_text" in result.agent_findings[0].evidence_ids


def test_high_bp_treatment_medication_scenario_moves_to_medical_review(service) -> None:
    job_id, base = _run_case_a(service)
    sim = service.simulate_underwriting_change(
        SimulateInput(
            job_id=job_id,
            changes=[
                ScenarioChange(field="health.blood_pressure.systolic", value=165),
                ScenarioChange(field="health.blood_pressure.diastolic", value=105),
                ScenarioChange(
                    field="medical.current_treatment.has_current_treatment",
                    value=True,
                ),
                ScenarioChange(
                    field="medical.current_treatment.conditions",
                    value=["hypertension"],
                ),
                ScenarioChange(field="medical.medications.has_medication", value=True),
                ScenarioChange(
                    field="medical.medications.items",
                    value=["antihypertensive"],
                ),
            ],
        )
    )

    assert base.recommendation.value == "ELIGIBLE_CANDIDATE"
    assert sim.recommendation_changed is True
    assert sim.base_recommendation == "ELIGIBLE_CANDIDATE"
    assert sim.scenario_recommendation == "REFER_MEDICAL_REVIEW"
    assert sim.after.recommendation == "REFER_MEDICAL_REVIEW"
    assert sim.after.missing_information
    assert set(sim.added_rule_hit_ids) == {
        "UW-BP-MEDICAL-001",
        "UW-TREATMENT-MEDICAL-001",
        "UW-MEDICATION-MEDICAL-001",
    }
    assert {
        "repeat_blood_pressure_measurement",
        "treatment_status",
        "medication_details",
        "physician_comment",
    } <= set(sim.added_missing_information)


def test_ambiguous_free_text_scenario_moves_to_info_request(service) -> None:
    job_id, base = _run_case_a(service)
    sim = service.simulate_underwriting_change(
        SimulateInput(
            job_id=job_id,
            changes=[
                ScenarioChange(
                    field="medical.disclosure.free_text",
                    value="医師から経過観察と再検査予定の指摘あり。",
                )
            ],
        )
    )
    assert base.recommendation.value == "ELIGIBLE_CANDIDATE"
    assert sim.recommendation_changed is True
    assert sim.scenario_recommendation == "REFER_INFO_REQUEST"
    assert sim.after.agent_finding_ids == ["AGENT-FREE-TEXT-001"]
    assert sim.added_agent_finding_ids == ["AGENT-FREE-TEXT-001"]
    assert {"follow_up_examination_result", "physician_comment"} <= set(
        sim.added_missing_information
    )


def test_invalid_scenario_path_fails_fast(service) -> None:
    job_id, _ = _run_case_a(service)
    with pytest.raises(ToolError) as exc:
        service.simulate_underwriting_change(
            SimulateInput(
                job_id=job_id,
                changes=[ScenarioChange(field="health.bp.systolic", value=165)],
            )
        )
    assert exc.value.code is ErrorCode.INVALID_INPUT
    assert "INVALID_SCENARIO_OVERRIDE_PATH" in exc.value.message


def test_v2_ruleset_file_exists() -> None:
    root = Path(__file__).resolve().parents[2]
    assert (root / "rulesets/demo-medical-2026-02/rules.yaml").is_file()
