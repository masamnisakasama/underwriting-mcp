"""in-process な WorkflowClient（mock mode, §22.2）。

Step Functions の代替として、抽出→ルール評価→結果組み立てを同期実行する。
段階（stage）を JobStore に反映し、artifacts を ObjectStore に保存する。
本番では同じ段階を Step Functions Standard で可視化する（§10.1）。
"""
from __future__ import annotations

from underwriting_core.assembly import assemble_result
from underwriting_core.rules.models import Ruleset

from ..clock import utcnow_iso
from ..models import CaseRecord, JobRecord, JobStatus, Stage
from ..ports import DocumentAnalyzer, JobStore, ObjectStore


class LocalWorkflowClient:
    def __init__(
        self,
        object_store: ObjectStore,
        job_store: JobStore,
        analyzer: DocumentAnalyzer,
        code_version: str | None = None,
    ) -> None:
        self._objects = object_store
        self._jobs = job_store
        self._analyzer = analyzer
        self._code_version = code_version

    def _advance(self, job: JobRecord, stage: Stage, percent: int) -> None:
        job.stage = stage
        job.progress_percent = percent
        job.status = JobStatus.PROCESSING
        job.updated_at = utcnow_iso()
        self._jobs.put_job(job)

    def start(self, case: CaseRecord, job: JobRecord, ruleset: Ruleset) -> None:
        created_at = job.created_at
        self._advance(job, Stage.EXTRACTING_DOCUMENTS, 35)
        facts = self._analyzer.analyze(case)
        facts_key = f"artifacts/{job.job_id}/canonical-facts.json"
        self._objects.put(facts_key, facts.model_dump_json(indent=2).encode("utf-8"))

        self._advance(job, Stage.EVALUATING_RULES, 70)
        result = assemble_result(
            facts=facts,
            ruleset=ruleset,
            case_id=case.case_id,
            job_id=job.job_id,
            created_at=created_at,
            completed_at=utcnow_iso(),
            document_hashes=case.document_hashes,
            code_version=self._code_version,
        )
        result_key = f"artifacts/{job.job_id}/decision-result.json"
        self._objects.put(result_key, result.model_dump_json(indent=2).encode("utf-8"))

        job.stage = Stage.DONE
        job.progress_percent = 100
        job.status = JobStatus.COMPLETED
        job.facts_uri = facts_key
        job.result_uri = result_key
        job.updated_at = utcnow_iso()
        self._jobs.put_job(job)
