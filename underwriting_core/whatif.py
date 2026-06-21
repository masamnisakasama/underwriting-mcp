"""What-if: canonical facts に変更を当てた写しを作る（§8.2 simulate）。

元の facts は変更しない（deep copy）。変更した項目は PRESENT 扱いにし、
合成 evidence を付けてガード（欠落・evidence なし）を再計算可能にする。
ルールの再評価は :func:`underwriting_core.assembly.assemble_result` 側で行う。
"""
from __future__ import annotations

from typing import Any, Iterable

from .canonical import CanonicalFacts, FactMeta
from .enums import FactStatus

ALLOWED_SCENARIO_PATHS: tuple[str, ...] = (
    "applicant.age",
    "application.coverage_amount",
    "health.blood_pressure.systolic",
    "health.blood_pressure.diastolic",
    "health.hba1c.value",
    "health.hba1c",
    "medical.current_treatment.has_current_treatment",
    "medical.current_treatment.conditions",
    "medical.current_treatment.free_text",
    "medical.current_treatment",
    "medical.medications.has_medication",
    "medical.medications.items",
    "medical.medications.free_text",
    "medical.current_medications",
    "medical.disclosure.has_health_check_abnormality",
    "medical.disclosure.has_hospitalization_history",
    "medical.disclosure.has_surgery_history",
    "medical.disclosure.free_text",
)


class ScenarioError(ValueError):
    """What-if 変更指定が不正。"""


def _set_nested(target: dict[str, Any], path: list[str], value: Any) -> None:
    node = target
    for part in path[:-1]:
        child = node.get(part)
        if not isinstance(child, dict):
            child = {}
            node[part] = child
        node = child
    node[path[-1]] = value


def apply_changes(
    facts: CanonicalFacts, changes: Iterable[tuple[str, Any]]
) -> CanonicalFacts:
    """``changes`` を当てた新しい :class:`CanonicalFacts` を返す。"""
    new = facts.model_copy(deep=True)
    for field, value in changes:
        if field not in ALLOWED_SCENARIO_PATHS:
            allowed = ", ".join(ALLOWED_SCENARIO_PATHS)
            raise ScenarioError(
                f"INVALID_SCENARIO_OVERRIDE_PATH: {field!r} は変更できません。"
                f" allowed_paths=[{allowed}]"
            )
        parts = field.split(".")
        root = parts[0]
        if root == "application":
            _set_nested(new.application, parts[1:], value)
            new.field_meta[field] = FactMeta(
                status=FactStatus.PRESENT, confidence=1.0, evidence_ids=["whatif"]
            )
            continue
        target = getattr(new, root)
        _set_nested(target, parts[1:], value)
        new.field_meta[field] = FactMeta(
            status=FactStatus.PRESENT, confidence=1.0, evidence_ids=["whatif"]
        )
    return new
