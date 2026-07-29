"""影テキスト検出器 -> 原文座標検出器 のアダプタ。

決定的検出器（正規表現・構造ルール・辞書）は「影テキスト（NFKC
正規化済み）」の上で動く方が単純になる（全角対応を吸収するため
半角前提で書ける）。本アダプタが正規化とスパン逆変換を一手に引き受け、
検出器本体を原文座標系から切り離す。
"""

from __future__ import annotations

from typing import Callable, Protocol, runtime_checkable

from namemask.normalize import NormalizedText, fold_normalize, normalize
from namemask.types import Span


@runtime_checkable
class ShadowDetector(Protocol):
    #: 検出根拠ラベル（Span.sources に載る）。
    name: str

    def detect_shadow(self, shadow: str) -> list[Span]:
        """影テキストを受け取り、影テキスト座標のスパンを返す。"""
        ...


class NormalizingDetector:
    """ShadowDetector を Detector（原文座標）に昇格するアダプタ。

    normalizer で影テキストの作り方を差し替えられる。既定は NFKC 影
    （正規表現層・構造ルール層向け）。辞書層は fold 影を使う。
    """

    def __init__(
        self,
        inner: ShadowDetector,
        normalizer: Callable[[str], NormalizedText] = normalize,
    ) -> None:
        self._inner = inner
        self.name = inner.name
        self._normalizer = normalizer

    def detect(self, text: str) -> list[Span]:
        norm = self._normalizer(text)
        shadow_spans = self._inner.detect_shadow(norm.shadow)
        return norm.map_spans(shadow_spans)


class FoldNormalizingDetector(NormalizingDetector):
    """辞書層用: fold 済み第2影テキスト上で照合するアダプタ。"""

    def __init__(self, inner: ShadowDetector) -> None:
        super().__init__(inner, normalizer=fold_normalize)
