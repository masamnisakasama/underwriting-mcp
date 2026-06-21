"""in-memory なポート実装（mock mode, §22.2）。

スレッド安全性は単一プロセスのデモ用途として最小限（dict + Lock）に留める。
"""
from __future__ import annotations

import threading

from ..models import CaseRecord, JobRecord, UploadTokenRecord


class InMemoryObjectStore:
    """S3 の代替。key -> bytes。"""

    def __init__(self) -> None:
        self._data: dict[str, bytes] = {}
        self._lock = threading.Lock()

    def put(self, key: str, data: bytes) -> str:
        with self._lock:
            self._data[key] = data
        return f"memory://{key}"

    def get(self, key: str) -> bytes:
        with self._lock:
            return self._data[key]

    def exists(self, key: str) -> bool:
        with self._lock:
            return key in self._data


class InMemoryJobStore:
    """DynamoDB の代替。case / job / idempotency を保持する。"""

    def __init__(self) -> None:
        self._cases: dict[str, CaseRecord] = {}
        self._jobs: dict[str, JobRecord] = {}
        self._idem: dict[str, str] = {}  # idempotency_key -> job_id
        self._upload_tokens: dict[str, UploadTokenRecord] = {}
        self._lock = threading.Lock()

    def put_case(self, case: CaseRecord) -> None:
        with self._lock:
            self._cases[case.case_id] = case.model_copy(deep=True)

    def get_case(self, case_id: str) -> CaseRecord | None:
        with self._lock:
            case = self._cases.get(case_id)
            return case.model_copy(deep=True) if case else None

    def list_cases(self) -> list[CaseRecord]:
        with self._lock:
            return [c.model_copy(deep=True) for c in self._cases.values()]

    def put_job(self, job: JobRecord) -> None:
        with self._lock:
            self._jobs[job.job_id] = job.model_copy(deep=True)
            self._idem[job.idempotency_key] = job.job_id

    def get_job(self, job_id: str) -> JobRecord | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return job.model_copy(deep=True) if job else None

    def get_job_by_idempotency(self, key: str) -> JobRecord | None:
        with self._lock:
            job_id = self._idem.get(key)
            job = self._jobs.get(job_id) if job_id else None
            return job.model_copy(deep=True) if job else None

    def list_jobs(self) -> list[JobRecord]:
        with self._lock:
            return [j.model_copy(deep=True) for j in self._jobs.values()]

    def put_upload_token(self, token: UploadTokenRecord) -> None:
        with self._lock:
            self._upload_tokens[token.token_hash] = token.model_copy(deep=True)

    def get_upload_token(self, token_hash: str) -> UploadTokenRecord | None:
        with self._lock:
            rec = self._upload_tokens.get(token_hash)
            return rec.model_copy(deep=True) if rec else None

    def set_upload_token_used(self, token_hash: str) -> None:
        with self._lock:
            rec = self._upload_tokens.get(token_hash)
            if rec is not None:
                rec.used = True
