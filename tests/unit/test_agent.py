from __future__ import annotations

from pathlib import Path

from underwriting_core.agent import assess_agent_findings
from underwriting_core.assembly import assemble_result
from underwriting_core.canonical import CanonicalFacts
from underwriting_core.enums import Recommendation
from underwriting_core.rules.loader import load_ruleset

RULESETS_DIR = Path(__file__).resolve().parents[2] / "rulesets"
V2_RULESET = load_ruleset(RULESETS_DIR, "demo-medical-2026-02")


def _facts(case_name: str) -> CanonicalFacts:
    path = Path(__file__).resolve().parents[2] / "samples" / case_name / "canonical-facts.json"
    return CanonicalFacts.model_validate_json(path.read_text("utf-8"))


def test_ambiguous_free_text_creates_agent_finding_with_source() -> None:
    findings = assess_agent_findings(_facts("case-d"))
    assert [f.finding_id for f in findings] == ["AGENT-FREE-TEXT-001"]
    finding = findings[0]
    assert finding.severity_suggestion is Recommendation.REFER_INFO_REQUEST
    assert finding.category == "ambiguous_disclosure"
    assert finding.field_path == "medical.disclosure.free_text"
    assert "再検査" in finding.source_text
    assert finding.evidence_ids == ["ev_d_disclosure_free_text"]
    assert "physician_comment" in finding.recommended_follow_up


def test_clean_case_has_no_agent_findings() -> None:
    assert assess_agent_findings(_facts("case-a")) == []


def test_agent_finding_can_raise_clean_case_to_info_request() -> None:
    facts = _facts("case-d")
    result = assemble_result(
        facts=facts,
        ruleset=V2_RULESET,
        case_id="uw_demo_case_d",
        job_id="job_d",
        created_at="2026-06-21T00:00:00Z",
        completed_at="2026-06-21T00:00:01Z",
    )
    assert result.recommendation is Recommendation.REFER_INFO_REQUEST
    assert result.rule_hits == []
    assert [f.finding_id for f in result.agent_findings] == ["AGENT-FREE-TEXT-001"]
    assert {"follow_up_examination_result", "physician_comment"} <= {
        m.field for m in result.missing_information
    }


def test_agent_finding_does_not_downgrade_guardrail() -> None:
    facts = _facts("case-d")
    facts.applicant["age"] = 75
    result = assemble_result(
        facts=facts,
        ruleset=V2_RULESET,
        case_id="uw_demo_case_d",
        job_id="job_d",
        created_at="2026-06-21T00:00:00Z",
        completed_at="2026-06-21T00:00:01Z",
    )
    assert result.recommendation is Recommendation.REFER_SENIOR_REVIEW
    assert "UW-AGE-SENIOR-001" in {h.rule_id for h in result.rule_hits}
    assert result.agent_findings
