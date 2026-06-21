"""ローカル mock end-to-end デモ（§27-5 / §31-3）。

AWS 不要。6 つの MCP tool 操作を service 経由で実行し、Case A/B/C の判定・根拠・
What-if・説明を標準出力に表示する。

    python scripts/run_mock_demo.py
"""
from __future__ import annotations

from underwriting_app.factory import build_mock_service
from underwriting_app.models import (
    ExplainInput,
    GetReviewInput,
    ScenarioChange,
    SimulateInput,
    StartReviewInput,
)
from underwriting_core.result import UnderwritingResult

RULESET_VERSION = "demo-medical-2026-01"


def _line(char: str = "-") -> None:
    print(char * 64)


def run() -> None:
    service = build_mock_service(code_version="mock-demo")

    _line("=")
    print("list_demo_cases")
    _line("=")
    for case in service.list_demo_cases():
        print(
            f"  {case.case_id}  {case.case_name:8s}  age={case.applicant_age:>3}  "
            f"expected={case.expected_recommendation}"
        )

    for case in service.list_demo_cases():
        _line("=")
        print(f"CASE {case.case_name}  ({case.case_id})")
        _line("=")
        start = service.start_underwriting_review(
            StartReviewInput(case_id=case.case_id, ruleset_version=RULESET_VERSION)
        )
        print(f"  start -> job_id={start.job_id} status={start.status.value}")

        result = service.get_underwriting_review(GetReviewInput(job_id=start.job_id))
        assert isinstance(result, UnderwritingResult)
        print(f"  recommendation : {result.recommendation.value} ({result.recommendation_label_ja})")
        print(f"  human_review   : {result.human_review_required}")
        print(f"  confidence     : {result.confidence}")
        print(f"  summary        : {result.summary_ja}")
        if result.rule_hits:
            print("  rule_hits:")
            for hit in result.rule_hits:
                print(
                    f"    - {hit.rule_id} [{hit.result.value}] {hit.reason_ja} "
                    f"evidence={hit.evidence_ids}"
                )
        if result.forced_refer_reasons:
            print(f"  forced_refer   : {result.forced_refer_reasons}")
        if result.contradictions:
            for con in result.contradictions:
                print(f"  contradiction  : {con.contradiction_id} {con.description_ja}")

    # explain（Case B）
    _line("=")
    print("explain_underwriting_review (case-b)")
    _line("=")
    start_b = service.start_underwriting_review(
        StartReviewInput(case_id="uw_demo_case_b", ruleset_version=RULESET_VERSION)
    )
    exp = service.explain_underwriting_review(
        ExplainInput(job_id=start_b.job_id, question="なぜ要査定なのですか")
    )
    print(f"  answerable : {exp.answerable}")
    print(f"  answer     : {exp.answer_ja}")
    print(f"  rule_ids   : {exp.rule_ids}")
    print(f"  evidence   : {exp.evidence_ids}")

    # simulate（Case B を健康側へ）
    _line("=")
    print("simulate_underwriting_change (case-b: 血圧/治療を健康側へ)")
    _line("=")
    sim = service.simulate_underwriting_change(
        SimulateInput(
            job_id=start_b.job_id,
            changes=[
                ScenarioChange(field="health.blood_pressure.systolic", value=128),
                ScenarioChange(field="health.blood_pressure.diastolic", value=78),
                ScenarioChange(field="medical.current_treatment", value=False),
            ],
        )
    )
    print(f"  before : {sim.before.recommendation} hits={sim.before.rule_hit_ids}")
    print(f"  after  : {sim.after.recommendation} hits={sim.after.rule_hit_ids}")
    print(f"  changed: {sim.changed_rule_hit_ids}")
    print(f"  note   : {sim.note_ja}")
    _line("=")
    print("DONE")


if __name__ == "__main__":
    run()
