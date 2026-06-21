"""Step Functions worker for Textract, Bedrock normalization, and result assembly."""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any, cast

import boto3
from pydantic import ValidationError

from underwriting_app.clock import utcnow_iso
from underwriting_app.models import CaseRecord, JobRecord, JobStatus, Stage
from underwriting_core.assembly import assemble_result
from underwriting_core.canonical import (
    CanonicalFacts,
    ContradictionItem,
    Evidence,
    FactMeta,
    MissingInfoItem,
)
from underwriting_core.enums import DocumentType, FactStatus, Severity
from underwriting_core.rules.loader import load_ruleset
from underwriting_core.result import UnderwritingResult

_ROOT = Path(__file__).resolve().parents[2]
_RULESETS_DIR = Path(os.environ.get("RULESETS_DIR", _ROOT / "rulesets"))


def _bucket() -> str:
    return os.environ["UNDERWRITING_BUCKET"]


def _table_name() -> str:
    return os.environ["UNDERWRITING_JOBS_TABLE"]


def _s3() -> Any:
    return boto3.client("s3")


def _table() -> Any:
    return boto3.resource("dynamodb").Table(_table_name())


def _textract() -> Any:
    return boto3.client("textract")


def _bedrock() -> Any:
    return boto3.client("bedrock-runtime")


def _get_payload(pk: str) -> dict[str, Any]:
    item = _table().get_item(Key={"pk": pk}).get("Item")
    if item is None:
        raise ValueError(f"Missing DynamoDB item: {pk}")
    return json.loads(cast(str, item["payload"]))


def _put_payload(pk: str, kind: str, payload: Any) -> None:
    if hasattr(payload, "model_dump_json"):
        body = payload.model_dump_json()
    else:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    _table().put_item(Item={"pk": pk, "kind": kind, "payload": body})


def _load_case(case_id: str) -> CaseRecord:
    return CaseRecord.model_validate(_get_payload(f"CASE#{case_id}"))


def _load_job(job_id: str) -> JobRecord:
    return JobRecord.model_validate(_get_payload(f"JOB#{job_id}"))


def _save_job(job: JobRecord) -> None:
    _put_payload(f"JOB#{job.job_id}", "JOB", job)


def _set_job(job_id: str, status: JobStatus, stage: Stage, progress: int) -> None:
    job = _load_job(job_id)
    job.status = status
    job.stage = stage
    job.progress_percent = progress
    job.updated_at = utcnow_iso()
    _save_job(job)


def _s3_put_json(key: str, data: Any) -> str:
    _s3().put_object(
        Bucket=_bucket(),
        Key=key,
        Body=json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"),
        ContentType="application/json",
    )
    return key


def _s3_get_json(key: str) -> Any:
    obj = _s3().get_object(Bucket=_bucket(), Key=key)
    return json.loads(obj["Body"].read().decode("utf-8"))


def _document_key(case_id: str, document_type: str) -> str:
    document_id = f"doc_{document_type.lower()}"
    return f"intake/{case_id}/{document_id}/original.pdf"


def validate_case(event: dict[str, Any]) -> dict[str, Any]:
    case = _load_case(cast(str, event["case_id"]))
    job = _load_job(cast(str, event["job_id"]))
    missing = set(case.expected_documents) - set(case.present_documents)
    if missing:
        job.status = JobStatus.FAILED
        job.error_code = "MISSING_REQUIRED_DOCUMENT"
        job.updated_at = utcnow_iso()
        _save_job(job)
        raise ValueError(f"Missing required documents: {[m.value for m in missing]}")

    _set_job(job.job_id, JobStatus.PROCESSING, Stage.VALIDATING, 5)
    return {
        **event,
        "documents": [
            {
                "document_type": dt.value,
                "s3_key": _document_key(case.case_id, dt.value),
                "file_name": case.uploaded_files.get(dt.value, f"{dt.value.lower()}.pdf"),
            }
            for dt in case.present_documents
        ],
        "created_at": job.created_at,
        "product_code": case.product_code,
    }


def _collect_textract_pages(textract_job_id: str) -> list[dict[str, Any]]:
    pages: list[dict[str, Any]] = []
    next_token: str | None = None
    while True:
        kwargs = {"JobId": textract_job_id}
        if next_token:
            kwargs["NextToken"] = next_token
        response = _textract().get_document_analysis(**kwargs)
        pages.extend(response.get("Blocks", []))
        next_token = response.get("NextToken")
        if not next_token:
            return pages


def _textract_lines(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    lines = []
    for block in blocks:
        if block.get("BlockType") != "LINE":
            continue
        geometry = block.get("Geometry", {}).get("BoundingBox")
        lines.append(
            {
                "page": int(block.get("Page", 1)),
                "text": block.get("Text", ""),
                "confidence": float(block.get("Confidence", 0.0)) / 100.0,
                "bounding_box": geometry,
                "block_id": block.get("Id"),
            }
        )
    return lines


def _demo_textract_lines(document_type: str) -> list[dict[str, Any]]:
    text_by_type = {
        "APPLICATION_FORM": [
            "Product code: DEMO_MEDICAL_01",
            "Age: 40",
            "Smoking status: NON_SMOKER",
            "Height cm: 170",
            "Weight kg: 64",
        ],
        "MEDICAL_DISCLOSURE": [
            "Current treatment: no",
            "Current medications: none",
            "Health exam finding: none",
        ],
        "HEALTH_CHECK": [
            "Blood pressure: 120 / 78 mmHg",
            "HbA1c: 5.4",
            "Overall judgment: normal",
        ],
    }
    return [
        {
            "page": 1,
            "text": text,
            "confidence": 0.99,
            "bounding_box": None,
            "block_id": f"demo-{document_type.lower()}-{index}",
        }
        for index, text in enumerate(text_by_type.get(document_type, []), start=1)
    ]


def process_document(event: dict[str, Any]) -> dict[str, Any]:
    case_id = cast(str, event["case_id"])
    job_id = cast(str, event["job_id"])
    doc = cast(dict[str, Any], event["document"])
    document_type = cast(str, doc["document_type"])
    _set_job(job_id, JobStatus.PROCESSING, Stage.EXTRACTING_DOCUMENTS, 25)

    if os.environ.get("DEMO_TEXTRACT_STUB") == "1":
        lines = _demo_textract_lines(document_type)
        artifact = {
            "case_id": case_id,
            "job_id": job_id,
            "document_type": document_type,
            "file_name": doc.get("file_name"),
            "textract_job_id": "demo-textract-stub",
            "lines": lines,
        }
        key = f"artifacts/{job_id}/textract/{document_type}.json"
        _s3_put_json(key, artifact)
        return {**doc, "artifact_key": key, "line_count": len(lines)}

    response = _textract().start_document_analysis(
        DocumentLocation={"S3Object": {"Bucket": _bucket(), "Name": doc["s3_key"]}},
        FeatureTypes=["FORMS", "TABLES", "SIGNATURES"],
    )
    textract_job_id = response["JobId"]
    deadline = time.time() + int(os.environ.get("TEXTRACT_WAIT_SECONDS", "240"))
    while True:
        status = _textract().get_document_analysis(JobId=textract_job_id, MaxResults=1)
        if status["JobStatus"] == "SUCCEEDED":
            break
        if status["JobStatus"] in {"FAILED", "PARTIAL_SUCCESS"}:
            raise RuntimeError(f"Textract failed for {document_type}: {status['JobStatus']}")
        if time.time() > deadline:
            raise TimeoutError(f"Timed out waiting for Textract job {textract_job_id}")
        time.sleep(5)

    blocks = _collect_textract_pages(textract_job_id)
    lines = _textract_lines(blocks)
    artifact = {
        "case_id": case_id,
        "job_id": job_id,
        "document_type": document_type,
        "file_name": doc.get("file_name"),
        "textract_job_id": textract_job_id,
        "lines": lines,
    }
    key = f"artifacts/{job_id}/textract/{document_type}.json"
    _s3_put_json(key, artifact)
    return {**doc, "artifact_key": key, "line_count": len(lines)}


def _full_text(document_artifacts: list[dict[str, Any]]) -> str:
    chunks = []
    for artifact in document_artifacts:
        doc = _s3_get_json(artifact["artifact_key"])
        chunks.append(f"## {doc['document_type']} {doc.get('file_name') or ''}")
        for line in doc["lines"]:
            chunks.append(f"[p{line['page']}] {line['text']}")
    return "\n".join(chunks)


def _match_int(pattern: str, text: str) -> int | None:
    match = re.search(pattern, text, re.IGNORECASE)
    return int(match.group(1)) if match else None


def _match_float(pattern: str, text: str) -> float | None:
    match = re.search(pattern, text, re.IGNORECASE)
    return float(match.group(1)) if match else None


def _deterministic_extract(text: str, event: dict[str, Any]) -> CanonicalFacts:
    age = _match_int(r"(?:age|年齢)\s*[:：]?\s*(\d+)", text)
    systolic = _match_int(r"(?:blood pressure|血圧)\s*[:：]?\s*(\d+)\s*/\s*\d+", text)
    diastolic = _match_int(r"(?:blood pressure|血圧)\s*[:：]?\s*\d+\s*/\s*(\d+)", text)
    hba1c = _match_float(r"HbA1c\s*[:：]?\s*([0-9.]+)", text)
    treatment_missing = re.search(r"current treatment\s*[:：]?\s*(missing|unknown)", text, re.I)
    treatment_no = re.search(r"current treatment\s*[:：]?\s*(no|false|いいえ)", text, re.I)
    health_exam_none = re.search(r"health exam finding\s*[:：]?\s*(none|なし)", text, re.I)
    health_exam_refer = re.search(r"overall judgment\s*[:：]?\s*(requires visit|要受診)", text, re.I)

    evidence: list[Evidence] = []
    field_meta: dict[str, FactMeta] = {}

    def add_ev(eid: str, field: str, raw: str, value: Any, doc_type: DocumentType) -> None:
        evidence.append(
            Evidence(
                evidence_id=eid,
                document_id=f"doc_{doc_type.value.lower()}",
                document_type=doc_type,
                file_name=f"{doc_type.value.lower()}.pdf",
                page=1,
                field=field,
                text=raw,
                normalized_value=value,
                confidence=0.9,
            )
        )

    if age is not None:
        add_ev("ev_age", "applicant.age", f"Age {age}", age, DocumentType.APPLICATION_FORM)
        field_meta["applicant.age"] = FactMeta(
            status=FactStatus.PRESENT, confidence=0.9, evidence_ids=["ev_age"]
        )
    if systolic is not None and diastolic is not None:
        add_ev(
            "ev_bp",
            "blood_pressure",
            f"{systolic} / {diastolic} mmHg",
            {"systolic": systolic, "diastolic": diastolic},
            DocumentType.HEALTH_CHECK,
        )
        field_meta["health.blood_pressure.systolic"] = FactMeta(
            status=FactStatus.PRESENT, confidence=0.9, evidence_ids=["ev_bp"]
        )
        field_meta["health.blood_pressure.diastolic"] = FactMeta(
            status=FactStatus.PRESENT, confidence=0.9, evidence_ids=["ev_bp"]
        )
    if hba1c is not None:
        add_ev("ev_hba1c", "hba1c", f"HbA1c {hba1c}", hba1c, DocumentType.HEALTH_CHECK)
        field_meta["health.hba1c"] = FactMeta(
            status=FactStatus.PRESENT, confidence=0.9, evidence_ids=["ev_hba1c"]
        )

    medical: dict[str, Any] = {
        "current_medications": [],
        "medications": {"has_medication": False, "items": [], "free_text": ""},
        "disclosure": {
            "has_health_check_abnormality": False,
            "has_hospitalization_history": False,
            "has_surgery_history": False,
            "free_text": "",
        },
    }
    missing: list[MissingInfoItem] = []
    if treatment_no:
        medical["current_treatment"] = {
            "has_current_treatment": False,
            "conditions": [],
            "free_text": "",
        }
        add_ev(
            "ev_treat",
            "current_treatment",
            "Current treatment: no",
            {"has_current_treatment": False},
            DocumentType.MEDICAL_DISCLOSURE,
        )
        field_meta["medical.current_treatment"] = FactMeta(
            status=FactStatus.PRESENT, confidence=0.9, evidence_ids=["ev_treat"]
        )
        field_meta["medical.current_treatment.has_current_treatment"] = FactMeta(
            status=FactStatus.PRESENT, confidence=0.9, evidence_ids=["ev_treat"]
        )
        field_meta["medical.medications.has_medication"] = FactMeta(
            status=FactStatus.PRESENT, confidence=0.9, evidence_ids=["ev_treat"]
        )
        field_meta["medical.disclosure.has_health_check_abnormality"] = FactMeta(
            status=FactStatus.PRESENT, confidence=0.9, evidence_ids=["ev_treat"]
        )
    elif treatment_missing:
        missing.append(
            MissingInfoItem(
                field="medical.current_treatment",
                reason_ja="治療状況が未記載です",
                severity=Severity.HIGH,
            )
        )
        field_meta["medical.current_treatment"] = FactMeta(status=FactStatus.MISSING)

    contradictions: list[ContradictionItem] = []
    if health_exam_none and health_exam_refer:
        medical.setdefault("disclosure", {})["has_health_check_abnormality"] = False
        contradictions.append(
            ContradictionItem(
                contradiction_id="con_001",
                key="health_exam",
                description_ja="告知書は健診異常なしですが、健診結果は要受診です",
                evidence_ids=["ev_disclosure_exam", "ev_health_exam"],
            )
        )
        add_ev(
            "ev_disclosure_exam",
            "health_exam_finding",
            "Health exam finding: none",
            "NONE",
            DocumentType.MEDICAL_DISCLOSURE,
        )
        add_ev(
            "ev_health_exam",
            "overall_judgment",
            "Overall judgment: requires visit",
            "REQUIRES_VISIT",
            DocumentType.HEALTH_CHECK,
        )

    expected = [DocumentType(d) for d in event.get("expected_documents", [])]
    present = [DocumentType(d["document_type"]) for d in event.get("document_artifacts", [])]
    return CanonicalFacts(
        applicant={"age": age, "product_code": event.get("product_code", "DEMO_MEDICAL_01")},
        health={"blood_pressure": {"systolic": systolic, "diastolic": diastolic}, "hba1c": hba1c},
        medical=medical,
        contradictions=contradictions,
        missing_information=missing,
        evidence=evidence,
        field_meta=field_meta,
        expected_documents=expected,
        present_documents=present,
        extraction_validation_failed=False,
    )


def _extract_json(text: str) -> str:
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if fenced:
        return fenced.group(1)
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start : end + 1]
    raise ValueError("Bedrock response did not contain JSON")


def _bedrock_extract(full_text: str, event: dict[str, Any]) -> CanonicalFacts:
    model_id = os.environ.get("BEDROCK_MODEL_ID")
    if not model_id or os.environ.get("DISABLE_BEDROCK_NORMALIZATION") == "1":
        return _deterministic_extract(full_text, event)

    prompt = (
        "Extract canonical underwriting demo facts as JSON matching this shape: "
        "{applicant, health, medical, contradictions, missing_information, evidence, "
        "field_meta, expected_documents, present_documents, extraction_validation_failed}. "
        "Use only document evidence. Do not decide underwriting recommendation.\n\n"
        f"{full_text}"
    )
    response = _bedrock().converse(
        modelId=model_id,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"temperature": 0, "maxTokens": 4096},
    )
    output_text = "".join(
        part.get("text", "")
        for part in response["output"]["message"]["content"]
        if "text" in part
    )
    try:
        return CanonicalFacts.model_validate_json(_extract_json(output_text))
    except (ValidationError, ValueError) as exc:
        repaired = _bedrock_repair(output_text, str(exc), event)
        if repaired is not None:
            return repaired
        repaired = _deterministic_extract(full_text, event)
        repaired.extraction_validation_failed = True
        return repaired


def _bedrock_repair(
    previous_output: str,
    validation_error: str,
    event: dict[str, Any],
) -> CanonicalFacts | None:
    model_id = os.environ.get("BEDROCK_MODEL_ID")
    if not model_id or os.environ.get("DISABLE_BEDROCK_NORMALIZATION") == "1":
        return None
    prompt = (
        "Repair the previous JSON so it validates as CanonicalFacts. "
        "Use only the previous extraction and validation errors. "
        "Do not add facts without evidence. Return JSON only.\n\n"
        f"expected_documents={event.get('expected_documents', [])}\n"
        f"document_artifacts={event.get('document_artifacts', [])}\n"
        f"validation_errors={validation_error}\n"
        f"previous_output={previous_output}"
    )
    response = _bedrock().converse(
        modelId=model_id,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"temperature": 0, "maxTokens": 4096},
    )
    output_text = "".join(
        part.get("text", "")
        for part in response["output"]["message"]["content"]
        if "text" in part
    )
    try:
        facts = CanonicalFacts.model_validate_json(_extract_json(output_text))
    except (ValidationError, ValueError):
        return None
    facts.extraction_validation_failed = False
    return facts


def _bedrock_narrative(result: UnderwritingResult) -> str | None:
    model_id = os.environ.get("BEDROCK_MODEL_ID")
    if not model_id or os.environ.get("DISABLE_BEDROCK_NARRATIVE") == "1":
        return None
    safe_result = {
        "recommendation": result.recommendation.value,
        "recommendation_label_ja": result.recommendation_label_ja,
        "missing_information": [m.model_dump(mode="json") for m in result.missing_information],
        "contradictions": [c.model_dump(mode="json") for c in result.contradictions],
        "rule_hits": [h.model_dump(mode="json") for h in result.rule_hits],
        "forced_refer_reasons": result.forced_refer_reasons,
        "disclaimer_ja": result.disclaimer_ja,
    }
    prompt = (
        "Write a concise Japanese underwriting support summary from this deterministic "
        "demo result. Do not change the recommendation. Do not invent medical diagnosis, "
        "criteria, or new rules. Return only the summary text.\n\n"
        f"{json.dumps(safe_result, ensure_ascii=False)}"
    )
    response = _bedrock().converse(
        modelId=model_id,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"temperature": 0, "maxTokens": 1024},
    )
    output_text = "".join(
        part.get("text", "")
        for part in response["output"]["message"]["content"]
        if "text" in part
    ).strip()
    return output_text[:1200] or None


def normalize(event: dict[str, Any]) -> dict[str, Any]:
    job_id = cast(str, event["job_id"])
    case = _load_case(cast(str, event["case_id"]))
    _set_job(job_id, JobStatus.PROCESSING, Stage.NORMALIZING, 60)
    event = {**event, "expected_documents": [d.value for d in case.expected_documents]}
    full_text = _full_text(cast(list[dict[str, Any]], event["document_artifacts"]))
    facts = _bedrock_extract(full_text, event)
    key = f"artifacts/{job_id}/canonical-facts.json"
    _s3_put_json(key, facts.model_dump(mode="json"))
    return {**event, "facts_uri": key}


def assemble(event: dict[str, Any]) -> dict[str, Any]:
    job = _load_job(cast(str, event["job_id"]))
    case = _load_case(cast(str, event["case_id"]))
    _set_job(job.job_id, JobStatus.PROCESSING, Stage.ASSEMBLING, 90)
    facts = CanonicalFacts.model_validate(_s3_get_json(cast(str, event["facts_uri"])))
    ruleset = load_ruleset(_RULESETS_DIR, cast(str, event["ruleset_version"]))
    result = assemble_result(
        facts=facts,
        ruleset=ruleset,
        case_id=case.case_id,
        job_id=job.job_id,
        created_at=job.created_at,
        completed_at=utcnow_iso(),
        model_id=os.environ.get("BEDROCK_MODEL_ID", "deterministic-fallback"),
        document_hashes=case.document_hashes,
        code_version=os.environ.get("CODE_VERSION"),
    )
    narrative = _bedrock_narrative(result)
    if narrative:
        result.summary_ja = narrative
    result_key = f"artifacts/{job.job_id}/decision-result.json"
    _s3_put_json(result_key, result.model_dump(mode="json"))
    facts_key = cast(str, event["facts_uri"])
    job.status = JobStatus.COMPLETED
    job.stage = Stage.DONE
    job.progress_percent = 100
    job.facts_uri = facts_key
    job.result_uri = result_key
    job.updated_at = utcnow_iso()
    _save_job(job)
    return {**event, "result_uri": result_key, "status": "COMPLETED"}


def mark_failed(event: dict[str, Any]) -> dict[str, Any]:
    job_id = cast(str, event["job_id"])
    job = _load_job(job_id)
    job.status = JobStatus.FAILED
    job.error_code = cast(dict[str, Any], event.get("error", {})).get(
        "Error", "INTERNAL_ERROR"
    )
    job.updated_at = utcnow_iso()
    _save_job(job)
    return {**event, "status": "FAILED"}


def handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    action = event.get("action")
    if action == "validate_case":
        return validate_case(event)
    if action == "process_document":
        return process_document(event)
    if action == "normalize":
        return normalize(event)
    if action == "assemble":
        return assemble(event)
    if action == "mark_failed":
        return mark_failed(event)
    raise ValueError(f"Unknown workflow action: {action}")
