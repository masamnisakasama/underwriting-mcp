"""AWS store adapters for APP_MODE=aws."""
from __future__ import annotations

import json
import os
from typing import Any, cast

import boto3

from underwriting_app.models import CaseRecord, JobRecord, UploadTokenRecord


class S3ObjectStore:
    def __init__(self, bucket: str | None = None) -> None:
        self._bucket = bucket or os.environ["UNDERWRITING_BUCKET"]
        self._s3 = boto3.client("s3")

    def put(self, key: str, data: bytes) -> str:
        self._s3.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=data,
        )
        return key

    def get(self, key: str) -> bytes:
        obj = self._s3.get_object(Bucket=self._bucket, Key=key)
        return obj["Body"].read()

    def exists(self, key: str) -> bool:
        try:
            self._s3.head_object(Bucket=self._bucket, Key=key)
        except self._s3.exceptions.ClientError:
            return False
        return True


class DynamoJobStore:
    def __init__(self, table_name: str | None = None) -> None:
        self._table_name = table_name or os.environ["UNDERWRITING_JOBS_TABLE"]
        self._table = boto3.resource("dynamodb").Table(self._table_name)

    def _put_model(self, pk: str, kind: str, model: Any) -> None:
        self._table.put_item(
            Item={
                "pk": pk,
                "kind": kind,
                "payload": model.model_dump_json(),
            }
        )

    def _get_payload(self, pk: str) -> dict[str, Any] | None:
        item = self._table.get_item(Key={"pk": pk}).get("Item")
        if item is None:
            return None
        return json.loads(cast(str, item["payload"]))

    def put_case(self, case: CaseRecord) -> None:
        self._put_model(f"CASE#{case.case_id}", "CASE", case)

    def get_case(self, case_id: str) -> CaseRecord | None:
        payload = self._get_payload(f"CASE#{case_id}")
        return CaseRecord.model_validate(payload) if payload else None

    def list_cases(self) -> list[CaseRecord]:
        response = self._table.scan(
            FilterExpression="#kind = :kind",
            ExpressionAttributeNames={"#kind": "kind"},
            ExpressionAttributeValues={":kind": "CASE"},
        )
        return [
            CaseRecord.model_validate_json(cast(str, item["payload"]))
            for item in response.get("Items", [])
        ]

    def put_job(self, job: JobRecord) -> None:
        self._put_model(f"JOB#{job.job_id}", "JOB", job)
        self._table.put_item(
            Item={
                "pk": f"IDEMPOTENCY#{job.idempotency_key}",
                "kind": "IDEMPOTENCY",
                "job_id": job.job_id,
            }
        )

    def get_job(self, job_id: str) -> JobRecord | None:
        payload = self._get_payload(f"JOB#{job_id}")
        return JobRecord.model_validate(payload) if payload else None

    def get_job_by_idempotency(self, key: str) -> JobRecord | None:
        item = self._table.get_item(Key={"pk": f"IDEMPOTENCY#{key}"}).get("Item")
        if item is None:
            return None
        return self.get_job(cast(str, item["job_id"]))

    def list_jobs(self) -> list[JobRecord]:
        response = self._table.scan(
            FilterExpression="#kind = :kind",
            ExpressionAttributeNames={"#kind": "kind"},
            ExpressionAttributeValues={":kind": "JOB"},
        )
        return [
            JobRecord.model_validate_json(cast(str, item["payload"]))
            for item in response.get("Items", [])
        ]

    def put_upload_token(self, token: UploadTokenRecord) -> None:
        self._put_model(f"UPLOAD#{token.token_hash}", "UPLOAD", token)

    def get_upload_token(self, token_hash: str) -> UploadTokenRecord | None:
        payload = self._get_payload(f"UPLOAD#{token_hash}")
        return UploadTokenRecord.model_validate(payload) if payload else None

    def set_upload_token_used(self, token_hash: str) -> None:
        rec = self.get_upload_token(token_hash)
        if rec is not None:
            rec.used = True
            self.put_upload_token(rec)
