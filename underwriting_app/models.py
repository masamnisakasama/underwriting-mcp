"""ケース/ジョブの状態モデルと、MCP tool の入出力モデル（§8.2 / §15.2）。"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from underwriting_core.enums import DocumentType


class JobStatus(str, Enum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Stage(str, Enum):
    VALIDATING = "VALIDATING"
    EXTRACTING_DOCUMENTS = "EXTRACTING_DOCUMENTS"
    NORMALIZING = "NORMALIZING"
    EVALUATING_RULES = "EVALUATING_RULES"
    ASSEMBLING = "ASSEMBLING"
    DONE = "DONE"


# -- 永続レコード（mock: in-memory / 本番: DynamoDB） -----------------------
class CaseRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    case_name: str
    product_code: str
    applicant_age: int
    expected_documents: list[DocumentType]
    present_documents: list[DocumentType] = Field(default_factory=list)
    # mock 専用：canonical facts fixture のキー（samples/<fixture_key>/）。
    fixture_key: str | None = None
    # mock 専用：デモ一覧で示す期待判定（samples/<key>/expected-result.json 由来）。
    expected_recommendation: str | None = None
    document_hashes: dict[str, str] = Field(default_factory=dict)
    document_page_counts: dict[str, int] = Field(default_factory=dict)
    uploaded_files: dict[str, str] = Field(default_factory=dict)
    created_at: str
    upload_expires_at: str


class UploadDocumentOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    document_type: DocumentType
    document_id: str
    sha256: str
    page_count: int
    sanitized_file_name: str
    status: str = "UPLOADED"


class UploadTokenRecord(BaseModel):
    """upload token のハッシュのみ保持（原文 token は保存しない, §7.3）。"""

    model_config = ConfigDict(extra="forbid")

    token_hash: str
    case_id: str
    document_type: DocumentType
    expires_at: str
    used: bool = False


class JobRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    case_id: str
    status: JobStatus
    stage: Stage
    progress_percent: int = 0
    ruleset_version: str
    idempotency_key: str
    result_uri: str | None = None
    facts_uri: str | None = None
    error_code: str | None = None
    created_at: str
    updated_at: str


# -- Tool I/O ---------------------------------------------------------------
class UploadSlot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_type: DocumentType
    upload_url: str
    upload_token: str


class CreateCaseInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_name: str
    product_code: str
    applicant_age: int
    expected_documents: list[DocumentType]
    # mock 専用：抽出（Textract/Bedrock）未実装段階でデモ事実を束ねる。
    demo_fixture: str | None = None


class CreateCaseOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    upload_expires_at: str
    uploads: list[UploadSlot]


class StartReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    ruleset_version: str


class StartReviewOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    status: JobStatus
    next_poll_after_seconds: int = 3


class GetReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str


class ReviewProgress(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    status: JobStatus
    stage: Stage
    progress_percent: int
    next_poll_after_seconds: int = 3


class ExplainInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    question: str


class ExplainOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answerable: bool
    answer_ja: str
    evidence_ids: list[str] = Field(default_factory=list)
    rule_ids: list[str] = Field(default_factory=list)


class ScenarioChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    value: object = None


class SimulateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    changes: list[ScenarioChange]


class ScenarioOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommendation: str
    recommendation_label_ja: str
    rule_hit_ids: list[str]
    agent_finding_ids: list[str] = Field(default_factory=list)
    forced_refer_reasons: list[str]
    missing_information: list[str] = Field(default_factory=list)


class SimulateOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    before: ScenarioOutcome
    after: ScenarioOutcome
    recommendation_changed: bool = False
    base_recommendation: str | None = None
    scenario_recommendation: str | None = None
    changed_rule_hit_ids: list[str]
    added_rule_hit_ids: list[str] = Field(default_factory=list)
    removed_rule_hit_ids: list[str] = Field(default_factory=list)
    added_agent_finding_ids: list[str] = Field(default_factory=list)
    added_missing_information: list[str] = Field(default_factory=list)
    note_ja: str = "What-if 比較であり、元の結果は変更していません。"


class DemoCaseSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    case_name: str
    product_code: str
    applicant_age: int
    expected_recommendation: str | None = None
