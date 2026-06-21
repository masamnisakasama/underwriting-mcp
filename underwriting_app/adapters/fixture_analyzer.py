"""fixture ベースの DocumentAnalyzer（mock mode, §22.2）。

実 Textract + Bedrock 抽出は AWS 段階（§27-7,8）で実装する。本アダプタは
``samples/<fixture_key>/canonical-facts.json`` を読み、確定 canonical facts を返す。
fixture が無いケース（実アップロード）は mock では処理できない旨を明示する。
"""
from __future__ import annotations

from pathlib import Path

from underwriting_core.canonical import CanonicalFacts

from ..errors import ErrorCode, ToolError
from ..models import CaseRecord


class FixtureDocumentAnalyzer:
    def __init__(self, samples_dir: str | Path) -> None:
        self._samples_dir = Path(samples_dir)

    def analyze(self, case: CaseRecord) -> CanonicalFacts:
        if not case.fixture_key:
            raise ToolError(
                ErrorCode.NOT_AVAILABLE_IN_MODE,
                "mock モードでは実アップロード帳票の抽出（Textract/Bedrock）は未実装です。",
                "list_demo_cases のデモケースを使うか、AWS 段階の抽出パイプラインを有効化してください。",
            )
        path = self._samples_dir / case.fixture_key / "canonical-facts.json"
        if not path.is_file():
            raise ToolError(
                ErrorCode.INTERNAL_ERROR,
                f"fixture canonical facts が見つかりません: {case.fixture_key}",
                "samples ディレクトリの整合性を確認してください。",
            )
        return CanonicalFacts.model_validate_json(path.read_text(encoding="utf-8"))
