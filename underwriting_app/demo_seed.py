"""デモケース（Case A/B/C）を JobStore へ事前登録する（§4 / §8.2 list_demo_cases）。

``samples/<case>/case.json`` をケースメタとして読み、fixture_key を当該ディレクトリに
束ねる。実アップロードではなく fixture canonical facts を使う mock 専用シード。
"""
from __future__ import annotations

import json
from pathlib import Path

from .clock import utcnow_iso
from .models import CaseRecord
from .ports import JobStore


def seed_demo_cases(job_store: JobStore, samples_dir: str | Path) -> list[str]:
    samples = Path(samples_dir)
    seeded: list[str] = []
    for case_dir in sorted(samples.glob("case-*")):
        case_json = case_dir / "case.json"
        if not case_json.is_file():
            continue
        data = json.loads(case_json.read_text(encoding="utf-8"))

        expected_rec = None
        expected_file = case_dir / "expected-result.json"
        if expected_file.is_file():
            expected_rec = json.loads(expected_file.read_text(encoding="utf-8")).get(
                "recommendation"
            )

        now = utcnow_iso()
        case = CaseRecord(
            case_id=data["case_id"],
            case_name=data["case_name"],
            product_code=data["product_code"],
            applicant_age=data["applicant_age"],
            expected_documents=data["expected_documents"],
            present_documents=data["expected_documents"],
            fixture_key=case_dir.name,
            expected_recommendation=expected_rec,
            document_hashes=data.get("document_hashes", {}),
            created_at=now,
            upload_expires_at=now,
        )
        job_store.put_case(case)
        seeded.append(case.case_id)
    return seeded
