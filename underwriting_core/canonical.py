"""Canonical Fact Model（§11）のデモ用サブセットと、ルール評価への橋渡し。

抽出（Textract + Bedrock）は AWS 段階（§27-7,8）で実装する。本モジュールは
その出力契約（= 確定した canonical facts）を表現し、決定論ルールエンジンが
参照する :class:`FactContext` へ変換する純粋ロジックに限定する（IO なし）。

不明値は 0/false/空文字で代用しない（§11）。値の有無は ``FactStatus`` と
``field_meta`` で明示的に表す。
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .enums import DocumentType, FactStatus, Severity
from .facts import FactContext

# 判定上「重要」とみなす項目。confidence 不足・evidence 欠落の強制 REFER 判定に使う。
IMPORTANT_FIELDS: tuple[str, ...] = (
    "applicant.age",
    "health.blood_pressure.systolic",
    "health.blood_pressure.diastolic",
    "health.hba1c",
    "health.hba1c.value",
    "medical.current_treatment",
    "medical.current_treatment.has_current_treatment",
    "medical.medications.has_medication",
)

# 重要項目 confidence の下限（§9.1）。これ未満は強制 REFER。
CONFIDENCE_FLOOR = 0.75


class BoundingBox(BaseModel):
    model_config = ConfigDict(extra="forbid")

    left: float
    top: float
    width: float
    height: float


class Evidence(BaseModel):
    """ページ単位で追跡可能な抽出根拠（§9 evidence）。"""

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


class FactMeta(BaseModel):
    """重要 fact のステータス・信頼度・根拠（§11 の per-fact メタ）。"""

    model_config = ConfigDict(extra="forbid")

    status: FactStatus = FactStatus.PRESENT
    confidence: float | None = None
    evidence_ids: list[str] = Field(default_factory=list)


class ContradictionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contradiction_id: str
    key: str  # ルールが参照する contradictions.<key> のキー
    description_ja: str
    evidence_ids: list[str] = Field(default_factory=list)


class MissingInfoItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    reason_ja: str
    severity: Severity = Severity.MEDIUM


class CanonicalFacts(BaseModel):
    """確定 canonical facts。抽出段の出力契約（§11 デモサブセット）。"""

    model_config = ConfigDict(extra="forbid")

    applicant: dict[str, Any] = Field(default_factory=dict)
    application: dict[str, Any] = Field(default_factory=dict)
    health: dict[str, Any] = Field(default_factory=dict)
    medical: dict[str, Any] = Field(default_factory=dict)
    contradictions: list[ContradictionItem] = Field(default_factory=list)
    missing_information: list[MissingInfoItem] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    field_meta: dict[str, FactMeta] = Field(default_factory=dict)
    expected_documents: list[DocumentType] = Field(default_factory=list)
    present_documents: list[DocumentType] = Field(default_factory=list)
    # 抽出段（Bedrock）の構造化検証が失敗したか（§19.2 / §10）。
    extraction_validation_failed: bool = False

    # -- ルール評価への変換 -------------------------------------------------
    def to_fact_context(self) -> FactContext:
        """ルール DSL が参照する :class:`FactContext` を構築する。"""
        values: dict[str, Any] = {
            "applicant": dict(self.applicant),
            "application": dict(self.application),
            "health": dict(self.health),
            "medical": dict(self.medical),
            "contradictions": {c.key: {"id": c.contradiction_id} for c in self.contradictions},
            "documents": {
                "expected": [d.value for d in self.expected_documents],
                "present": [d.value for d in self.present_documents],
            },
        }
        statuses = {path: meta.status for path, meta in self.field_meta.items()}
        return FactContext(values=values, statuses=statuses)

    def evidence_ids_for(self, field: str) -> list[str]:
        meta = self.field_meta.get(field)
        return list(meta.evidence_ids) if meta else []
