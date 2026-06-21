"""ルールDSL全演算子のユニットテスト（§24.1 rule DSL全演算子）。"""
from __future__ import annotations

import pytest

from underwriting_core.enums import FactStatus
from underwriting_core.facts import FactContext
from underwriting_core.rules import dsl
from underwriting_core.rules.dsl import RuleEvaluationError

CTX = FactContext(
    values={
        "applicant": {"age": 52, "smoking_status": "NON_SMOKER"},
        "health": {"blood_pressure": {"systolic": 165, "diastolic": 105}, "hba1c": 5.8},
        "medical": {"current_treatment": False, "medications": ["aspirin"]},
        "contradictions": {"health_exam": {"id": "con_001"}},
    },
)


@pytest.mark.parametrize(
    "condition, expected",
    [
        ({"eq": {"field": "applicant.age", "value": 52}}, True),
        ({"eq": {"field": "applicant.age", "value": 40}}, False),
        ({"neq": {"field": "applicant.age", "value": 40}}, True),
        ({"gt": {"field": "health.blood_pressure.systolic", "value": 160}}, True),
        ({"gt": {"field": "health.blood_pressure.systolic", "value": 165}}, False),
        ({"gte": {"field": "health.blood_pressure.systolic", "value": 165}}, True),
        ({"lt": {"field": "health.hba1c", "value": 6.0}}, True),
        ({"lte": {"field": "health.hba1c", "value": 5.8}}, True),
        ({"in": {"field": "applicant.smoking_status", "value": ["SMOKER", "NON_SMOKER"]}}, True),
        ({"in": {"field": "applicant.smoking_status", "value": ["SMOKER"]}}, False),
        ({"contains": {"field": "medical.medications", "value": "aspirin"}}, True),
        ({"contains": {"field": "medical.medications", "value": "warfarin"}}, False),
        ({"exists": {"field": "contradictions.health_exam"}}, True),
        ({"exists": {"field": "contradictions.unknown"}}, False),
        ({"is_missing": {"field": "medical.diagnosis"}}, True),
        ({"is_missing": {"field": "applicant.age"}}, False),
    ],
)
def test_leaf_operators(condition: dict, expected: bool) -> None:
    assert dsl.evaluate(condition, CTX) is expected


def test_false_value_is_not_missing() -> None:
    # False は実在値であり「欠落」ではない（§11: 0/false で代用しない）。
    assert dsl.evaluate({"is_missing": {"field": "medical.current_treatment"}}, CTX) is False
    assert dsl.evaluate({"exists": {"field": "medical.current_treatment"}}, CTX) is True


def test_missing_value_comparison_is_false() -> None:
    # 欠落値を推測で埋めない → 比較は常に False。
    assert dsl.evaluate({"gte": {"field": "medical.unknown_num", "value": 1}}, CTX) is False


def test_and_or_not() -> None:
    cond = {
        "and": [
            {"gte": {"field": "health.blood_pressure.systolic", "value": 160}},
            {"not": {"is_missing": {"field": "applicant.age"}}},
        ]
    }
    assert dsl.evaluate(cond, CTX) is True
    assert dsl.evaluate({"or": [{"eq": {"field": "applicant.age", "value": 1}}, {"eq": {"field": "applicant.age", "value": 52}}]}, CTX) is True


def test_unknown_operator_raises() -> None:
    with pytest.raises(RuleEvaluationError):
        dsl.evaluate({"regex": {"field": "applicant.age", "value": ".*"}}, CTX)


def test_malformed_condition_raises() -> None:
    with pytest.raises(RuleEvaluationError):
        dsl.evaluate({"eq": {"field": "applicant.age"}}, CTX)  # value欠落
    with pytest.raises(RuleEvaluationError):
        dsl.evaluate({"gt": {}, "lt": {}}, CTX)  # 演算子2つ


def test_referenced_fields_collects_nested_paths() -> None:
    cond = {
        "and": [
            {"or": [
                {"gte": {"field": "health.blood_pressure.systolic", "value": 160}},
                {"gte": {"field": "health.blood_pressure.diastolic", "value": 100}},
            ]},
            {"is_missing": {"field": "medical.current_treatment"}},
        ]
    }
    assert dsl.referenced_fields(cond) == [
        "health.blood_pressure.systolic",
        "health.blood_pressure.diastolic",
        "medical.current_treatment",
    ]


def test_status_override_marks_missing() -> None:
    ctx = FactContext(
        values={"medical": {"current_treatment": True}},
        statuses={"medical.current_treatment": FactStatus.AMBIGUOUS},
    )
    # AMBIGUOUS は欠落扱いではない（PRESENT扱い）。値はあるので exists True。
    assert ctx.exists("medical.current_treatment") is True
    ctx2 = FactContext(
        values={"medical": {"current_treatment": True}},
        statuses={"medical.current_treatment": FactStatus.NOT_APPLICABLE},
    )
    assert dsl.evaluate({"is_missing": {"field": "medical.current_treatment"}}, ctx2) is True
