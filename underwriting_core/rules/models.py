"""ルール / ルールセットの Pydantic モデル（§12）。"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..enums import Recommendation


class Rule(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str
    rule_type: str = Field(default="screening_rule", alias="type")
    name: str | None = None
    priority: int = 0
    description_ja: str = ""
    when: dict[str, Any]
    result: Recommendation
    human_review_required: bool = False
    reason_ja: str = ""
    required_information: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _accept_v2_yaml(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        normalized = dict(data)
        if "result" not in normalized and "outcome" in normalized:
            normalized["result"] = normalized.pop("outcome")
        if "description_ja" not in normalized and "name" in normalized:
            normalized["description_ja"] = normalized["name"]
        if "reason_ja" not in normalized and "reason" in normalized:
            normalized["reason_ja"] = normalized.pop("reason")
        return normalized


class Ruleset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ruleset_version: str
    product_code: str
    description: str = ""
    outcome_order: list[Recommendation] = Field(default_factory=list)
    rules: list[Rule]

    @model_validator(mode="before")
    @classmethod
    def _accept_v2_yaml(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        normalized = dict(data)
        if "ruleset_version" not in normalized and "ruleset_id" in normalized:
            normalized["ruleset_version"] = normalized.pop("ruleset_id")
        return normalized

    def sorted_rules(self) -> list[Rule]:
        """priority 降順（高い順）で評価する。"""
        return sorted(self.rules, key=lambda r: r.priority, reverse=True)
