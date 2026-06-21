"""外部システムのポート（抽象境界, §22.1）。

実装をモック（ローカル）と AWS で差し替えられるよう Protocol で定義する。
ドメインロジックはこれらにのみ依存し、boto3 等を直接 import しない。

- ObjectStore  -> S3（mock: in-memory）
- JobStore     -> DynamoDB（mock: in-memory）
- DocumentAnalyzer -> Textract + Bedrock 抽出（mock: fixture canonical facts）
- WorkflowClient   -> Step Functions（mock: in-process 同期パイプライン）

ModelClient（Bedrock）は Bedrock 抽出段（§27-8）で追加する。
"""
from __future__ import annotations

from typing import Protocol

from underwriting_core.canonical import CanonicalFacts
from underwriting_core.rules.models import Ruleset

from .models import CaseRecord, JobRecord, UploadTokenRecord


class ObjectStore(Protocol):
    def put(self, key: str, data: bytes) -> str:
        """データを保存し URI を返す。"""

    def get(self, key: str) -> bytes: ...

    def exists(self, key: str) -> bool: ...


class JobStore(Protocol):
    def put_case(self, case: CaseRecord) -> None: ...

    def get_case(self, case_id: str) -> CaseRecord | None: ...

    def list_cases(self) -> list[CaseRecord]: ...

    def put_job(self, job: JobRecord) -> None: ...

    def get_job(self, job_id: str) -> JobRecord | None: ...

    def get_job_by_idempotency(self, key: str) -> JobRecord | None: ...

    def list_jobs(self) -> list[JobRecord]: ...

    def put_upload_token(self, token: UploadTokenRecord) -> None: ...

    def get_upload_token(self, token_hash: str) -> UploadTokenRecord | None: ...

    def set_upload_token_used(self, token_hash: str) -> None: ...


class DocumentAnalyzer(Protocol):
    def analyze(self, case: CaseRecord) -> CanonicalFacts:
        """ケースのアップロード帳票から確定 canonical facts を生成する。"""


class WorkflowClient(Protocol):
    def start(self, case: CaseRecord, job: JobRecord, ruleset: Ruleset) -> None:
        """査定ワークフローを起動する（mock は同期実行）。"""
