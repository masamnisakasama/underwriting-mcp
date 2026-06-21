"""Underwriting Result Schema（§9）の Pydantic 実装。

``schemas/underwriting-result.schema.json`` と同じ意味を持つ。MCP tool の
``structuredContent`` / ``outputSchema`` として使う。
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .canonical import BoundingBox
from .enums import DocumentType, Recommendation, Severity

SCHEMA_VERSION = "1.0.0"
DISCLAIMER_JA = (
    "本結果はデモ用ルールに基づく判断支援であり、最終的な保険引受判断ではありません。"
)


class MissingInformation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    reason_ja: str
    severity: Severity


class ContradictionOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contradiction_id: str
    description_ja: str
    evidence_ids: list[str] = Field(default_factory=list)


class RuleHitOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_id: str
    result: Recommendation
    reason_ja: str
    evidence_ids: list[str] = Field(default_factory=list)


class AgentFindingOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    finding_id: str
    severity_suggestion: Recommendation
    category: str
    description_ja: str
    field_path: str
    source_text: str
    evidence_ids: list[str] = Field(default_factory=list)
    recommended_follow_up: list[str] = Field(default_factory=list)
    confidence: float


class EvidenceOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    document_id: str
    document_type: DocumentType
    file_name: str
    page: int
    field: str
    text: str
    normalized_value: Any = None
    confidence: float
    bounding_box: BoundingBox | None = None
    source_block_ids: list[str] = Field(default_factory=list)


class UnderwritingResult(BaseModel):
    """最終結果（§9）。LLM の自称判定ではなく決定論エンジンの結果を反映する。"""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCHEMA_VERSION
    case_id: str
    job_id: str
    status: str = "COMPLETED"
    recommendation: Recommendation
    recommendation_label_ja: str
    human_review_required: bool
    confidence: float
    summary_ja: str
    disclaimer_ja: str = DISCLAIMER_JA
    applicant_facts: dict[str, Any] = Field(default_factory=dict)
    health_facts: dict[str, Any] = Field(default_factory=dict)
    missing_information: list[MissingInformation] = Field(default_factory=list)
    contradictions: list[ContradictionOut] = Field(default_factory=list)
    forced_refer_reasons: list[str] = Field(default_factory=list)
    rule_hits: list[RuleHitOut] = Field(default_factory=list)
    agent_findings: list[AgentFindingOut] = Field(default_factory=list)
    evidence: list[EvidenceOut] = Field(default_factory=list)
    ruleset_version: str
    model_id: str = "mock"
    document_hashes: dict[str, str] = Field(default_factory=dict)
    code_version: str | None = None
    workflow_execution_arn: str | None = None
    created_at: str
    completed_at: str
