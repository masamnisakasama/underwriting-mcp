from __future__ import annotations

import json

from lambdas.underwriting_workflow import app
from lambdas.underwriting_workflow.app import _bedrock_narrative, _bedrock_repair, _deterministic_extract
from underwriting_core.assembly import assemble_result
from underwriting_core.enums import FactStatus
from underwriting_core.rules.loader import load_ruleset

from pathlib import Path

RULESETS_DIR = Path(__file__).resolve().parents[2] / "rulesets"


def test_deterministic_extract_case_b_signals() -> None:
    text = "\n".join(
        [
            "Age: 52",
            "Blood pressure: 165 / 105 mmHg",
            "HbA1c: 5.8",
            "Current treatment: missing",
            "Health exam finding: none",
            "Overall judgment: requires visit",
        ]
    )
    facts = _deterministic_extract(
        text,
        {
            "product_code": "DEMO_MEDICAL_01",
            "expected_documents": [
                "APPLICATION_FORM",
                "MEDICAL_DISCLOSURE",
                "HEALTH_CHECK",
            ],
            "document_artifacts": [
                {"document_type": "APPLICATION_FORM"},
                {"document_type": "MEDICAL_DISCLOSURE"},
                {"document_type": "HEALTH_CHECK"},
            ],
        },
    )
    assert facts.applicant["age"] == 52
    assert facts.health["blood_pressure"]["systolic"] == 165
    assert facts.field_meta["medical.current_treatment"].status is FactStatus.MISSING
    assert facts.contradictions[0].key == "health_exam"


def test_bedrock_repair_uses_validation_errors(monkeypatch) -> None:
    facts = _deterministic_extract(
        "Age: 40\nBlood pressure: 120 / 78 mmHg\nHbA1c: 5.4\nCurrent treatment: no",
        {
            "product_code": "DEMO_MEDICAL_01",
            "expected_documents": ["APPLICATION_FORM", "MEDICAL_DISCLOSURE", "HEALTH_CHECK"],
            "document_artifacts": [
                {"document_type": "APPLICATION_FORM"},
                {"document_type": "MEDICAL_DISCLOSURE"},
                {"document_type": "HEALTH_CHECK"},
            ],
        },
    )

    class FakeBedrock:
        def converse(self, **_: object) -> dict[str, object]:
            return {
                "output": {
                    "message": {
                        "content": [
                            {"text": "```json\n" + facts.model_dump_json() + "\n```"}
                        ]
                    }
                }
            }

    monkeypatch.setenv("BEDROCK_MODEL_ID", "demo-model")
    monkeypatch.setattr(app, "_bedrock", lambda: FakeBedrock())
    repaired = _bedrock_repair("bad json", "missing field", {})
    assert repaired is not None
    assert repaired.extraction_validation_failed is False
    assert repaired.applicant["age"] == 40


def test_bedrock_narrative_returns_summary_text(monkeypatch) -> None:
    facts = _deterministic_extract(
        "Age: 40\nBlood pressure: 120 / 78 mmHg\nHbA1c: 5.4\nCurrent treatment: no",
        {
            "product_code": "DEMO_MEDICAL_01",
            "expected_documents": ["APPLICATION_FORM", "MEDICAL_DISCLOSURE", "HEALTH_CHECK"],
            "document_artifacts": [
                {"document_type": "APPLICATION_FORM"},
                {"document_type": "MEDICAL_DISCLOSURE"},
                {"document_type": "HEALTH_CHECK"},
            ],
        },
    )
    result = assemble_result(
        facts=facts,
        ruleset=load_ruleset(RULESETS_DIR, "demo-medical-2026-01"),
        case_id="uw_test",
        job_id="job_test",
        created_at="2026-06-20T10:00:00Z",
        completed_at="2026-06-20T10:00:01Z",
    )

    class FakeBedrock:
        def converse(self, **kwargs: object) -> dict[str, object]:
            payload = json.dumps(kwargs, ensure_ascii=False)
            assert "ELIGIBLE_CANDIDATE" in payload
            return {"output": {"message": {"content": [{"text": "引受候補です。"}]}}}

    monkeypatch.setenv("BEDROCK_MODEL_ID", "demo-model")
    monkeypatch.setattr(app, "_bedrock", lambda: FakeBedrock())
    assert _bedrock_narrative(result) == "引受候補です。"
