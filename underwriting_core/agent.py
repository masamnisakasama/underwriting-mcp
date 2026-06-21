"""Underwriting agent findings for ambiguous, non-deterministic review signals.

This module is intentionally pure and deterministic for the demo. A later AWS
implementation can replace the detector with Bedrock-backed assessment while
keeping the same output contract.
"""
from __future__ import annotations

from typing import Any, Mapping

from .canonical import CanonicalFacts
from .enums import Recommendation
from .result import AgentFindingOut


AMBIGUOUS_REVIEW_TERMS: tuple[str, ...] = (
    "再検査",
    "精密検査",
    "経過観察",
    "要受診",
    "医師",
    "指摘",
    "follow-up",
    "follow up",
    "retest",
    "observation",
)


def _nested_get(data: Mapping[str, Any], path: str) -> Any:
    node: Any = data
    for part in path.split("."):
        if not isinstance(node, Mapping) or part not in node:
            return None
        node = node[part]
    return node


def _evidence_ids(facts: CanonicalFacts, field_path: str) -> list[str]:
    ids = facts.evidence_ids_for(field_path)
    if ids:
        return ids
    parent = field_path.rsplit(".", 1)[0]
    return facts.evidence_ids_for(parent)


def _text_for_field(facts: CanonicalFacts, field_path: str) -> str:
    if field_path.startswith("medical."):
        value = _nested_get(facts.medical, field_path.removeprefix("medical."))
    elif field_path.startswith("health."):
        value = _nested_get(facts.health, field_path.removeprefix("health."))
    elif field_path.startswith("applicant."):
        value = _nested_get(facts.applicant, field_path.removeprefix("applicant."))
    else:
        value = None
    return value if isinstance(value, str) else ""


def assess_agent_findings(facts: CanonicalFacts) -> list[AgentFindingOut]:
    """Detect review-worthy ambiguous text that deterministic rules do not own."""
    findings: list[AgentFindingOut] = []
    candidates = [
        (
            "medical.disclosure.free_text",
            "ambiguous_disclosure",
            "告知自由記述に追加確認が必要な曖昧表現があります。",
            ["follow_up_examination_result", "physician_comment"],
        ),
        (
            "medical.current_treatment.free_text",
            "ambiguous_treatment_status",
            "治療状況の自由記述に追加確認が必要な曖昧表現があります。",
            ["latest_status", "physician_comment"],
        ),
        (
            "medical.medications.free_text",
            "ambiguous_medication",
            "服薬自由記述に処方理由や用量の追加確認が必要な表現があります。",
            ["medication_name", "dosage", "prescribing_condition"],
        ),
    ]

    for index, (field_path, category, description, follow_up) in enumerate(candidates, start=1):
        source_text = _text_for_field(facts, field_path)
        if not source_text:
            continue
        lowered = source_text.lower()
        if not any(term.lower() in lowered for term in AMBIGUOUS_REVIEW_TERMS):
            continue
        evidence_ids = _evidence_ids(facts, field_path)
        findings.append(
            AgentFindingOut(
                finding_id=f"AGENT-FREE-TEXT-{index:03d}",
                severity_suggestion=Recommendation.REFER_INFO_REQUEST,
                category=category,
                description_ja=description,
                field_path=field_path,
                source_text=source_text,
                evidence_ids=evidence_ids,
                recommended_follow_up=follow_up,
                confidence=0.78,
            )
        )
    return findings
