"""6 つの MCP tool 操作（§8.2）をポート越しに実装する。

トランスポート非依存。HTTP/MCP 層（§27-10）はこの service を呼ぶだけにする。
最終 recommendation は決定論エンジン（``underwriting_core``）でのみ決まる。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from underwriting_core.assembly import assemble_result
from underwriting_core.enums import DocumentType
from underwriting_core.explain import explain as explain_result
from underwriting_core.result import UnderwritingResult
from underwriting_core.rules.loader import RulesetNotFoundError, load_ruleset
from underwriting_core.rules.models import Ruleset
from underwriting_core.whatif import ScenarioError, apply_changes

from .clock import utcnow_iso
from .errors import ErrorCode, ToolError
from .ids import (
    hash_token,
    idempotency_key,
    new_case_id,
    new_job_id,
    new_upload_token,
)
from .models import (
    CaseRecord,
    CreateCaseInput,
    CreateCaseOutput,
    DemoCaseSummary,
    ExplainInput,
    ExplainOutput,
    GetReviewInput,
    JobRecord,
    JobStatus,
    ReviewProgress,
    ScenarioOutcome,
    SimulateInput,
    SimulateOutput,
    Stage,
    StartReviewInput,
    StartReviewOutput,
    UploadDocumentOutput,
    UploadSlot,
    UploadTokenRecord,
)
from .ports import JobStore, ObjectStore, WorkflowClient
from .upload_validation import (
    MAX_FILES_PER_CASE,
    MAX_PAGES_PER_CASE,
    sanitize_filename,
    validate_pdf,
)

UPLOAD_TTL_SECONDS = 600


def _parse_iso(ts: str) -> datetime:
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


class UnderwritingService:
    def __init__(
        self,
        *,
        object_store: ObjectStore,
        job_store: JobStore,
        workflow: WorkflowClient,
        rulesets_dir: str | Path,
        public_base_url: str = "https://underwriting-mcp.local",
        demo_mode: bool = True,
    ) -> None:
        self._objects = object_store
        self._jobs = job_store
        self._workflow = workflow
        self._rulesets_dir = Path(rulesets_dir)
        self._base_url = public_base_url.rstrip("/")
        self._demo_mode = demo_mode

    # -- ruleset ------------------------------------------------------------
    def _load_ruleset(self, ruleset_version: str) -> Ruleset:
        try:
            return load_ruleset(self._rulesets_dir, ruleset_version)
        except RulesetNotFoundError as exc:
            raise ToolError(
                ErrorCode.RULESET_NOT_FOUND,
                f"ruleset が見つかりません: {ruleset_version}",
                "list_demo_cases / 設定済み ruleset_version を確認してください。",
            ) from exc

    # -- create_underwriting_case ------------------------------------------
    def create_underwriting_case(self, payload: CreateCaseInput) -> CreateCaseOutput:
        if not (0 < payload.applicant_age < 120):
            raise ToolError(
                ErrorCode.INVALID_INPUT,
                "applicant_age が不正です。",
                "1〜119 の整数で applicant_age を指定してください。",
            )
        if not payload.expected_documents:
            raise ToolError(
                ErrorCode.INVALID_INPUT,
                "expected_documents が空です。",
                "少なくとも 1 種類の帳票種別を指定してください。",
            )

        case_id = new_case_id()
        now = utcnow_iso()
        expires = (
            datetime.now(timezone.utc) + timedelta(seconds=UPLOAD_TTL_SECONDS)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")

        uploads: list[UploadSlot] = []
        for dt in payload.expected_documents:
            token = new_upload_token()
            uploads.append(
                UploadSlot(
                    document_type=dt,
                    upload_url=f"{self._base_url}/v1/cases/{case_id}/documents/{dt.value}",
                    upload_token=token,
                )
            )
            self._jobs.put_upload_token(
                UploadTokenRecord(
                    token_hash=hash_token(token),
                    case_id=case_id,
                    document_type=dt,
                    expires_at=expires,
                )
            )

        # mock: demo_fixture 指定時はアップロード済みとして束ねる。実抽出は AWS 段階。
        present = list(payload.expected_documents) if payload.demo_fixture else []
        case = CaseRecord(
            case_id=case_id,
            case_name=payload.case_name,
            product_code=payload.product_code,
            applicant_age=payload.applicant_age,
            expected_documents=payload.expected_documents,
            present_documents=present,
            fixture_key=payload.demo_fixture,
            created_at=now,
            upload_expires_at=expires,
        )
        self._jobs.put_case(case)
        return CreateCaseOutput(
            case_id=case_id, upload_expires_at=expires, uploads=uploads
        )

    # -- Upload API --------------------------------------------------------
    def upload_document(
        self,
        *,
        case_id: str,
        document_type: DocumentType,
        upload_token: str,
        filename: str,
        data: bytes,
        content_type: str | None = None,
        declared_size: int | None = None,
    ) -> UploadDocumentOutput:
        case = self._jobs.get_case(case_id)
        if case is None:
            raise ToolError(
                ErrorCode.CASE_NOT_FOUND,
                f"case が見つかりません: {case_id}",
                "create_underwriting_case が返した upload_url を使用してください。",
            )
        if document_type not in case.expected_documents:
            raise ToolError(
                ErrorCode.INVALID_INPUT,
                f"この case では {document_type.value} のアップロードは予定されていません。",
                "create_underwriting_case の expected_documents を確認してください。",
            )

        rec = self._jobs.get_upload_token(hash_token(upload_token))
        if rec is None or rec.case_id != case_id or rec.document_type != document_type:
            raise ToolError(
                ErrorCode.INVALID_INPUT,
                "upload token が case または document type と一致しません。",
                "create_underwriting_case で発行された該当帳票用 token を使用してください。",
            )
        if rec.used:
            raise ToolError(
                ErrorCode.UPLOAD_TOKEN_ALREADY_USED,
                "upload token は既に使用済みです。",
                "case を作り直して新しい upload token を取得してください。",
            )
        if datetime.now(timezone.utc) > _parse_iso(rec.expires_at):
            raise ToolError(
                ErrorCode.UPLOAD_TOKEN_EXPIRED,
                "upload token の有効期限が切れています。",
                "case を作り直して新しい upload token を取得してください。",
            )

        sha256, page_count = validate_pdf(
            data, declared_size=declared_size, content_type=content_type
        )
        if (
            len(case.present_documents) >= MAX_FILES_PER_CASE
            and document_type not in case.present_documents
        ):
            raise ToolError(
                ErrorCode.INVALID_INPUT,
                f"1ケースのファイル数上限（{MAX_FILES_PER_CASE}）を超えています。",
                "帳票を5ファイル以内に整理して再作成してください。",
            )
        total_pages = sum(case.document_page_counts.values()) + page_count
        previous_pages = case.document_page_counts.get(document_type.value, 0)
        total_pages -= previous_pages
        if total_pages > MAX_PAGES_PER_CASE:
            raise ToolError(
                ErrorCode.PAGE_LIMIT_EXCEEDED,
                f"1ケースの合計ページ数（{total_pages}）が"
                f"上限（{MAX_PAGES_PER_CASE}）を超えています。",
                "対象帳票を合計30ページ以内にしてください。",
            )

        safe_name = sanitize_filename(filename)
        document_id = f"doc_{document_type.value.lower()}"
        key = f"intake/{case_id}/{document_id}/original.pdf"
        self._objects.put(key, data)

        case.document_hashes[document_type.value] = sha256
        case.document_page_counts[document_type.value] = page_count
        case.uploaded_files[document_type.value] = safe_name
        if document_type not in case.present_documents:
            case.present_documents.append(document_type)
        self._jobs.put_case(case)
        self._jobs.set_upload_token_used(rec.token_hash)

        return UploadDocumentOutput(
            case_id=case_id,
            document_type=document_type,
            document_id=document_id,
            sha256=sha256,
            page_count=page_count,
            sanitized_file_name=safe_name,
        )

    # -- start_underwriting_review -----------------------------------------
    def start_underwriting_review(self, payload: StartReviewInput) -> StartReviewOutput:
        case = self._jobs.get_case(payload.case_id)
        if case is None:
            raise ToolError(
                ErrorCode.CASE_NOT_FOUND,
                f"case が見つかりません: {payload.case_id}",
                "create_underwriting_case で作成した case_id を指定してください。",
            )
        ruleset = self._load_ruleset(payload.ruleset_version)

        idem = idempotency_key(
            payload.case_id, payload.ruleset_version, case.document_hashes
        )
        existing = self._jobs.get_job_by_idempotency(idem)
        if existing is not None:
            return StartReviewOutput(job_id=existing.job_id, status=existing.status)

        now = utcnow_iso()
        job = JobRecord(
            job_id=new_job_id(),
            case_id=payload.case_id,
            status=JobStatus.QUEUED,
            stage=Stage.VALIDATING,
            progress_percent=0,
            ruleset_version=payload.ruleset_version,
            idempotency_key=idem,
            created_at=now,
            updated_at=now,
        )
        self._jobs.put_job(job)

        try:
            self._workflow.start(case, job, ruleset)
        except ToolError as exc:
            job.status = JobStatus.FAILED
            job.error_code = exc.code.value
            job.updated_at = utcnow_iso()
            self._jobs.put_job(job)
            raise

        latest = self._jobs.get_job(job.job_id)
        assert latest is not None
        return StartReviewOutput(job_id=latest.job_id, status=latest.status)

    # -- get_underwriting_review -------------------------------------------
    def _require_job(self, job_id: str) -> JobRecord:
        job = self._jobs.get_job(job_id)
        if job is None:
            raise ToolError(
                ErrorCode.JOB_NOT_FOUND,
                f"job が見つかりません: {job_id}",
                "start_underwriting_review が返した job_id を指定してください。",
            )
        return job

    def _load_result(self, job: JobRecord) -> UnderwritingResult:
        assert job.result_uri is not None
        raw = self._objects.get(job.result_uri)
        return UnderwritingResult.model_validate_json(raw)

    def get_underwriting_review(
        self, payload: GetReviewInput
    ) -> UnderwritingResult | ReviewProgress:
        job = self._require_job(payload.job_id)
        if job.status is JobStatus.COMPLETED:
            return self._load_result(job)
        if job.status is JobStatus.FAILED:
            try:
                code = ErrorCode(job.error_code or ErrorCode.INTERNAL_ERROR.value)
            except ValueError:
                code = ErrorCode.INTERNAL_ERROR
            raise ToolError(
                code,
                "査定ジョブが失敗しました。",
                "入力帳票・ruleset を確認のうえ再実行してください。",
            )
        return ReviewProgress(
            job_id=job.job_id,
            status=job.status,
            stage=job.stage,
            progress_percent=job.progress_percent,
        )

    # -- explain_underwriting_review ---------------------------------------
    def explain_underwriting_review(self, payload: ExplainInput) -> ExplainOutput:
        if not payload.question.strip():
            raise ToolError(
                ErrorCode.INVALID_INPUT,
                "question が空です。",
                "結果に対する質問文を指定してください。",
            )
        job = self._require_completed(payload.job_id)
        result = self._load_result(job)
        exp = explain_result(result, payload.question)
        return ExplainOutput(
            answerable=exp.answerable,
            answer_ja=exp.answer_ja,
            evidence_ids=exp.evidence_ids,
            rule_ids=exp.rule_ids,
        )

    # -- simulate_underwriting_change --------------------------------------
    def simulate_underwriting_change(self, payload: SimulateInput) -> SimulateOutput:
        if not payload.changes:
            raise ToolError(
                ErrorCode.INVALID_INPUT,
                "changes が空です。",
                "field と value を含む変更を 1 件以上指定してください。",
            )
        job = self._require_completed(payload.job_id)
        ruleset = self._load_ruleset(job.ruleset_version)

        from underwriting_core.canonical import CanonicalFacts

        assert job.facts_uri is not None
        facts = CanonicalFacts.model_validate_json(self._objects.get(job.facts_uri))
        try:
            after_facts = apply_changes(
                facts, [(c.field, c.value) for c in payload.changes]
            )
        except ScenarioError as exc:
            raise ToolError(
                ErrorCode.INVALID_INPUT, str(exc), "変更可能な項目パスを指定してください。"
            ) from exc

        ts = utcnow_iso()
        before = assemble_result(
            facts=facts, ruleset=ruleset, case_id=job.case_id,
            job_id=f"{job.job_id}#before", created_at=ts, completed_at=ts,
        )
        after = assemble_result(
            facts=after_facts, ruleset=ruleset, case_id=job.case_id,
            job_id=f"{job.job_id}#after", created_at=ts, completed_at=ts,
        )
        before_ids = {h.rule_id for h in before.rule_hits}
        after_ids = {h.rule_id for h in after.rule_hits}
        before_agent_ids = {f.finding_id for f in before.agent_findings}
        after_agent_ids = {f.finding_id for f in after.agent_findings}
        before_missing = {m.field for m in before.missing_information}
        after_missing = {m.field for m in after.missing_information}
        changed = sorted(before_ids ^ after_ids)
        return SimulateOutput(
            before=_outcome(before),
            after=_outcome(after),
            recommendation_changed=before.recommendation != after.recommendation,
            base_recommendation=before.recommendation.value,
            scenario_recommendation=after.recommendation.value,
            changed_rule_hit_ids=changed,
            added_rule_hit_ids=sorted(after_ids - before_ids),
            removed_rule_hit_ids=sorted(before_ids - after_ids),
            added_agent_finding_ids=sorted(after_agent_ids - before_agent_ids),
            added_missing_information=sorted(after_missing - before_missing),
        )

    def _require_completed(self, job_id: str) -> JobRecord:
        job = self._require_job(job_id)
        if job.status is not JobStatus.COMPLETED:
            raise ToolError(
                ErrorCode.JOB_NOT_FOUND if job.status is JobStatus.FAILED
                else ErrorCode.INVALID_INPUT,
                "結果がまだ利用できません。",
                "get_underwriting_review が COMPLETED を返してから実行してください。",
            )
        return job

    # -- MCP Resources（§8.3）----------------------------------------------
    def _latest_completed_job_for_case(self, case_id: str) -> JobRecord:
        if self._jobs.get_case(case_id) is None:
            raise ToolError(
                ErrorCode.CASE_NOT_FOUND,
                f"case が見つかりません: {case_id}",
                "存在する case_id を指定してください。",
            )
        jobs = [
            j
            for j in self._jobs.list_jobs()
            if j.case_id == case_id and j.status is JobStatus.COMPLETED
        ]
        if not jobs:
            raise ToolError(
                ErrorCode.JOB_NOT_FOUND,
                f"完了済みの査定結果がありません: case={case_id}",
                "start_underwriting_review を実行し COMPLETED を待ってください。",
            )
        return max(jobs, key=lambda j: j.updated_at)

    def result_for_case(self, case_id: str) -> UnderwritingResult:
        return self._load_result(self._latest_completed_job_for_case(case_id))

    def evidence_for_case(self, case_id: str) -> list[dict[str, object]]:
        result = self.result_for_case(case_id)
        # 原文 PDF は返さず、ページ追跡可能な evidence メタのみ返す（§8.3）。
        return [e.model_dump(mode="json") for e in result.evidence]

    def ruleset_definition(self, ruleset_version: str) -> dict[str, object]:
        ruleset = self._load_ruleset(ruleset_version)
        return ruleset.model_dump(mode="json")

    # -- list_demo_cases ----------------------------------------------------
    def list_demo_cases(self) -> list[DemoCaseSummary]:
        if not self._demo_mode:
            raise ToolError(
                ErrorCode.NOT_AVAILABLE_IN_MODE,
                "list_demo_cases は demo モードでのみ有効です。",
                "ENVIRONMENT=demo で起動してください。",
            )
        summaries = [
            DemoCaseSummary(
                case_id=c.case_id,
                case_name=c.case_name,
                product_code=c.product_code,
                applicant_age=c.applicant_age,
                expected_recommendation=c.expected_recommendation,
            )
            for c in self._jobs.list_cases()
            if c.fixture_key is not None
        ]
        return sorted(summaries, key=lambda s: s.case_name)


def _outcome(result: UnderwritingResult) -> ScenarioOutcome:
    return ScenarioOutcome(
        recommendation=result.recommendation.value,
        recommendation_label_ja=result.recommendation_label_ja,
        rule_hit_ids=[h.rule_id for h in result.rule_hits],
        agent_finding_ids=[f.finding_id for f in result.agent_findings],
        forced_refer_reasons=result.forced_refer_reasons,
        missing_information=[m.field for m in result.missing_information],
    )
