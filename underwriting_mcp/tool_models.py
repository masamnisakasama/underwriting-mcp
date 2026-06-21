"""MCP tool 専用の入出力エンベロープ。"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from underwriting_app.models import ReviewProgress
from underwriting_core.result import UnderwritingResult


class GetReviewResponse(BaseModel):
    """get_underwriting_review の単一 outputSchema（進行中 or 完了を内包）。"""

    model_config = ConfigDict(extra="forbid")

    completed: bool
    result: UnderwritingResult | None = None
    progress: ReviewProgress | None = None
