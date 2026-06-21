"""固定の列挙値。仕様書 §1.判定区分 / §11.Fact status に対応。"""
from __future__ import annotations

from enum import Enum


class Recommendation(str, Enum):
    """引受の判断候補（最終判定ではなく支援）。"""

    ELIGIBLE_CANDIDATE = "ELIGIBLE_CANDIDATE"
    REFER_INFO_REQUEST = "REFER_INFO_REQUEST"
    REFER_MEDICAL_REVIEW = "REFER_MEDICAL_REVIEW"
    REFER_SENIOR_REVIEW = "REFER_SENIOR_REVIEW"
    DECLINE_CANDIDATE = "DECLINE_CANDIDATE"
    # v1 compatibility. New rulesets should use the explicit v2 categories above.
    REFER = "REFER"
    NOT_ELIGIBLE_CANDIDATE = "NOT_ELIGIBLE_CANDIDATE"

    @property
    def label_ja(self) -> str:
        return {
            "ELIGIBLE_CANDIDATE": "引受候補",
            "REFER_INFO_REQUEST": "追加照会",
            "REFER_MEDICAL_REVIEW": "医務査定回付",
            "REFER_SENIOR_REVIEW": "上位査定回付",
            "DECLINE_CANDIDATE": "引受不可候補",
            "REFER": "要査定",
            "NOT_ELIGIBLE_CANDIDATE": "引受不可候補",
        }[self.value]

    @property
    def severity(self) -> int:
        """深刻度。値が大きいほど「より厳しい」判定。

        precedence: DECLINE > SENIOR > MEDICAL/REFER > INFO > ELIGIBLE。
        複数候補があるときは severity 最大を採用する。
        """
        return {
            "ELIGIBLE_CANDIDATE": 0,
            "REFER_INFO_REQUEST": 1,
            "REFER": 2,
            "REFER_MEDICAL_REVIEW": 2,
            "REFER_SENIOR_REVIEW": 3,
            "DECLINE_CANDIDATE": 4,
            "NOT_ELIGIBLE_CANDIDATE": 4,
        }[self.value]


class FactStatus(str, Enum):
    """canonical fact の状態（§11）。不明値を空文字・0・false で代用しないための区別。"""

    PRESENT = "PRESENT"
    MISSING = "MISSING"
    AMBIGUOUS = "AMBIGUOUS"
    CONTRADICTED = "CONTRADICTED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class DocumentType(str, Enum):
    """対象帳票種別（§7.2）。"""

    APPLICATION_FORM = "APPLICATION_FORM"
    MEDICAL_DISCLOSURE = "MEDICAL_DISCLOSURE"
    HEALTH_CHECK = "HEALTH_CHECK"
    SUPPLEMENTAL = "SUPPLEMENTAL"


class Severity(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
