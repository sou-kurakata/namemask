"""検出器の共通プロトコル。

すべての検出層は「原文を受け取り、原文座標の Span を返す」だけの契約。
eval.py はこの Protocol に対して層別寄与を計測する（層を差し替え可能に保つ）。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from namemask.types import Span


@runtime_checkable
class Detector(Protocol):
    #: 検出根拠ラベル（Span.sources に載る）。SOURCE_PRIORITY のキーと対応。
    name: str

    def detect(self, text: str) -> list[Span]:
        """原文を受け取り、原文座標のスパン集合を返す（重複は許容）。"""
        ...
