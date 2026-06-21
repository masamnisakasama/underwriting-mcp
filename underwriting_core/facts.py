"""ルールDSLが参照する事実コンテキスト。

canonical facts（ネストした dict）をドット区切りパスで解決し、
「値が存在するか / 欠落か」を `FactStatus` も踏まえて判定する。
不明値を 0/false/空文字 で代用しないため、値の有無は明示的に扱う（§11）。
"""
from __future__ import annotations

from typing import Any, Mapping

from .enums import FactStatus

_MISSING = object()


class FactContext:
    """ルール評価用の読み取り専用ビュー。

    Args:
        values: ネストした事実の dict。例 ``{"applicant": {"age": 52}}``。
        statuses: ドット区切りパス -> FactStatus の明示マップ（任意）。
            指定があれば値より優先して欠落判定に使う。
    """

    def __init__(
        self,
        values: Mapping[str, Any] | None = None,
        statuses: Mapping[str, FactStatus] | None = None,
    ) -> None:
        self._values: dict[str, Any] = dict(values or {})
        self._statuses: dict[str, FactStatus] = dict(statuses or {})

    # -- 値解決 -------------------------------------------------------------
    def _resolve(self, path: str) -> Any:
        """ドット区切りパスを辿る。見つからなければ ``_MISSING`` を返す。"""
        node: Any = self._values
        for part in path.split("."):
            if isinstance(node, Mapping) and part in node:
                node = node[part]
            else:
                return _MISSING
        return node

    def get(self, path: str) -> Any:
        """値を返す。欠落時は ``None``。"""
        value = self._resolve(path)
        return None if value is _MISSING else value

    def status(self, path: str) -> FactStatus:
        if path in self._statuses:
            return self._statuses[path]
        value = self._resolve(path)
        if value is _MISSING or value is None:
            return FactStatus.MISSING
        return FactStatus.PRESENT

    # -- 述語 ---------------------------------------------------------------
    def is_missing(self, path: str) -> bool:
        return self.status(path) in (FactStatus.MISSING, FactStatus.NOT_APPLICABLE)

    def exists(self, path: str) -> bool:
        """値が実在し、欠落/非該当でないこと。"""
        return not self.is_missing(path) and self.get(path) is not None
