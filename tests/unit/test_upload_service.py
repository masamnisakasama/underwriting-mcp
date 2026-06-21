from __future__ import annotations

import pytest

from scripts.generate_sample_pdfs import build_pdf
from underwriting_app.errors import ErrorCode, ToolError
from underwriting_app.factory import build_mock_service
from underwriting_app.models import CreateCaseInput
from underwriting_core.enums import DocumentType


def _pdf(pages: int = 1) -> bytes:
    return build_pdf([[f"page {i}"] for i in range(pages)])


def test_upload_document_single_use_token() -> None:
    service = build_mock_service(seed_demos=False)
    created = service.create_underwriting_case(
        CreateCaseInput(
            case_name="upload",
            product_code="DEMO_MEDICAL_01",
            applicant_age=40,
            expected_documents=[DocumentType.APPLICATION_FORM],
        )
    )
    slot = created.uploads[0]
    result = service.upload_document(
        case_id=created.case_id,
        document_type=DocumentType.APPLICATION_FORM,
        upload_token=slot.upload_token,
        filename="../application form.pdf",
        data=_pdf(),
        content_type="application/pdf",
    )
    assert result.status == "UPLOADED"
    assert result.sha256.startswith("sha256:")
    assert result.sanitized_file_name == "application_form.pdf"

    with pytest.raises(ToolError) as exc:
        service.upload_document(
            case_id=created.case_id,
            document_type=DocumentType.APPLICATION_FORM,
            upload_token=slot.upload_token,
            filename="again.pdf",
            data=_pdf(),
            content_type="application/pdf",
        )
    assert exc.value.code is ErrorCode.UPLOAD_TOKEN_ALREADY_USED


def test_upload_rejects_non_pdf_content_type() -> None:
    service = build_mock_service(seed_demos=False)
    created = service.create_underwriting_case(
        CreateCaseInput(
            case_name="upload",
            product_code="DEMO_MEDICAL_01",
            applicant_age=40,
            expected_documents=[DocumentType.APPLICATION_FORM],
        )
    )
    with pytest.raises(ToolError) as exc:
        service.upload_document(
            case_id=created.case_id,
            document_type=DocumentType.APPLICATION_FORM,
            upload_token=created.uploads[0].upload_token,
            filename="bad.txt",
            data=b"not pdf",
            content_type="text/plain",
        )
    assert exc.value.code is ErrorCode.UNSUPPORTED_FILE_TYPE
