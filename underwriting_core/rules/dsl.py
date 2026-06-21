"""ルール条件 DSL の評価器（§12.3）。

サポート演算子のみを実装し、``eval`` は一切使わない（安全性）。
条件は「演算子1つをキーに持つ dict」。

    {"gte": {"field": "health.blood_pressure.systolic", "value": 160}}
    {"and": [<cond>, <cond>, ...]}
    {"is_missing": {"field": "medical.current_treatment"}}

不明な演算子や不正な構造は ``RuleEvaluationError`` を送出する。
"""
from __future__ import annotations

from typing import Any, Callable, Mapping

from ..facts import FactContext

SUPPORTED_OPERATORS = (
    "eq", "neq", "gt", "gte", "lt", "lte", "in", "contains",
    "exists", "is_missing", "and", "or", "not", "all", "any",
    "required_documents",
)


class RuleEvaluationError(ValueError):
    """条件の構造不正・未対応演算子。エラーコード RULE_EVALUATION_FAILED に対応。"""


def evaluate(condition: Mapping[str, Any], ctx: FactContext) -> bool:
    """条件を評価して真偽を返す。"""
    if _is_v2_field_condition(condition):
        return _evaluate_v2_field_condition(condition, ctx)
    if not isinstance(condition, Mapping) or len(condition) != 1:
        raise RuleEvaluationError(
            f"condition は演算子1つを持つ object である必要があります: {condition!r}"
        )
    (operator, operand), = condition.items()
    handler = _HANDLERS.get(operator)
    if handler is None:
        raise RuleEvaluationError(f"未対応の演算子: {operator!r}")
    return handler(operand, ctx)


def referenced_fields(condition: Mapping[str, Any]) -> list[str]:
    """条件木が参照する全 ``field`` パスを順序維持・重複排除で返す。

    rule hit の evidence 紐付け（どの抽出項目が根拠か）に使う。
    """
    found: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, Mapping):
            if isinstance(node.get("field"), str):
                field = node["field"]
                if field not in found:
                    found.append(field)
            for value in node.values():
                walk(value)
        elif isinstance(node, (list, tuple)):
            for item in node:
                walk(item)

    walk(condition)
    return found


# -- 個別演算子 -------------------------------------------------------------
def _is_v2_field_condition(condition: Mapping[str, Any]) -> bool:
    return "field" in condition and "op" in condition


def _evaluate_v2_field_condition(condition: Mapping[str, Any], ctx: FactContext) -> bool:
    op = condition.get("op")
    if not isinstance(op, str):
        raise RuleEvaluationError(f"op は文字列である必要があります: {condition!r}")
    operand = {"field": condition.get("field"), "value": condition.get("value")}
    if op == "exists":
        return _op_exists({"field": condition.get("field")}, ctx)
    if op == "is_missing":
        return _op_is_missing({"field": condition.get("field")}, ctx)
    handler = _HANDLERS.get(op)
    if handler is None:
        raise RuleEvaluationError(f"未対応の op: {op!r}")
    return handler(operand, ctx)


def _field_and_value(operand: Any) -> tuple[str, Any]:
    if not isinstance(operand, Mapping) or "field" not in operand or "value" not in operand:
        raise RuleEvaluationError(f"{{'field','value'}} が必要です: {operand!r}")
    field = operand["field"]
    if not isinstance(field, str):
        raise RuleEvaluationError(f"field は文字列である必要があります: {field!r}")
    return field, operand["value"]


def _field_only(operand: Any) -> str:
    if not isinstance(operand, Mapping) or "field" not in operand:
        raise RuleEvaluationError(f"{{'field'}} が必要です: {operand!r}")
    field = operand["field"]
    if not isinstance(field, str):
        raise RuleEvaluationError(f"field は文字列である必要があります: {field!r}")
    return field


def _numeric_compare(operand: Any, ctx: FactContext, op: Callable[[Any, Any], bool]) -> bool:
    field, threshold = _field_and_value(operand)
    actual = ctx.get(field)
    if actual is None:  # 欠落値は比較不能 → False（推測しない）
        return False
    try:
        return op(actual, threshold)
    except TypeError:
        return False


def _op_eq(operand: Any, ctx: FactContext) -> bool:
    field, value = _field_and_value(operand)
    return ctx.get(field) == value


def _op_neq(operand: Any, ctx: FactContext) -> bool:
    return not _op_eq(operand, ctx)


def _op_in(operand: Any, ctx: FactContext) -> bool:
    field, value = _field_and_value(operand)
    if not isinstance(value, (list, tuple, set)):
        raise RuleEvaluationError(f"'in' の value は配列である必要があります: {value!r}")
    return ctx.get(field) in value


def _op_contains(operand: Any, ctx: FactContext) -> bool:
    field, value = _field_and_value(operand)
    actual = ctx.get(field)
    if actual is None:
        return False
    try:
        return value in actual
    except TypeError:
        return False


def _op_exists(operand: Any, ctx: FactContext) -> bool:
    return ctx.exists(_field_only(operand))


def _op_is_missing(operand: Any, ctx: FactContext) -> bool:
    return ctx.is_missing(_field_only(operand))


def _op_and(operand: Any, ctx: FactContext) -> bool:
    if not isinstance(operand, list):
        raise RuleEvaluationError(f"'and' は配列が必要です: {operand!r}")
    return all(evaluate(cond, ctx) for cond in operand)


def _op_or(operand: Any, ctx: FactContext) -> bool:
    if not isinstance(operand, list):
        raise RuleEvaluationError(f"'or' は配列が必要です: {operand!r}")
    return any(evaluate(cond, ctx) for cond in operand)


def _op_required_documents(operand: Any, ctx: FactContext) -> bool:
    if not isinstance(operand, list):
        raise RuleEvaluationError(f"'required_documents' は配列が必要です: {operand!r}")
    present = ctx.get("documents.present") or []
    return bool(set(operand) - set(present))


def _op_not(operand: Any, ctx: FactContext) -> bool:
    return not evaluate(operand, ctx)


_HANDLERS: dict[str, Callable[[Any, FactContext], bool]] = {
    "eq": _op_eq,
    "neq": _op_neq,
    "gt": lambda o, c: _numeric_compare(o, c, lambda a, b: a > b),
    "gte": lambda o, c: _numeric_compare(o, c, lambda a, b: a >= b),
    "lt": lambda o, c: _numeric_compare(o, c, lambda a, b: a < b),
    "lte": lambda o, c: _numeric_compare(o, c, lambda a, b: a <= b),
    "in": _op_in,
    "contains": _op_contains,
    "exists": _op_exists,
    "is_missing": _op_is_missing,
    "and": _op_and,
    "or": _op_or,
    "all": _op_and,
    "any": _op_or,
    "required_documents": _op_required_documents,
    "not": _op_not,
}
