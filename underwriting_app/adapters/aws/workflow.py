"""Step Functions workflow client for APP_MODE=aws."""
from __future__ import annotations

import json
import os

import boto3

from underwriting_core.rules.models import Ruleset

from ...clock import utcnow_iso
from ...models import CaseRecord, JobRecord, JobStatus
from ...ports import JobStore


class StepFunctionsWorkflowClient:
    def __init__(self, job_store: JobStore, state_machine_arn: str | None = None) -> None:
        self._jobs = job_store
        self._arn = state_machine_arn or os.environ["UNDERWRITING_STATE_MACHINE_ARN"]
        self._sfn = boto3.client("stepfunctions")

    def start(self, case: CaseRecord, job: JobRecord, ruleset: Ruleset) -> None:
        self._sfn.start_execution(
            stateMachineArn=self._arn,
            name=job.job_id.replace("_", "-"),
            input=json.dumps(
                {
                    "case_id": case.case_id,
                    "job_id": job.job_id,
                    "ruleset_version": ruleset.ruleset_version,
                    "document_hashes": case.document_hashes,
                },
                separators=(",", ":"),
            ),
        )
        job.status = JobStatus.QUEUED
        job.updated_at = utcnow_iso()
        job.result_uri = None
        self._jobs.put_job(job)
