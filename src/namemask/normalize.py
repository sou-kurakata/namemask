"""正規化層 — 影テキスト＋charmap。

原文を **1文字ずつ** NFKC 正規化して「影テキスト」を作り、同時に
`影テキストの各文字 -> 原文インデックス` の charmap を構築する。
以降の全検出は影テキスト上で行い、スパンは charmap で原文座標へ逆変換する。
原文は決して書き換えない。

NFKC は 1->複数文字の展開がある（㈱ -> (株) で 1->3、全角英数 -> 半角）。
charmap で必ず追跡し、置換は常に原文座標に対して行う。

注意（既知の限界）: NFKC を「1文字ずつ」適用するため、原文で別々の
コードポイントに分かれた合成列（例: 半角カナ ｶ + 濁点 ﾞ）は結合されない
（全文 NFKC なら ガ に合成される）。座標対応の厳密性を優先した仕様上の
トレードオフ。主対象の全角英数・全角記号・㈱ は単一文字展開で
影響を受けない。半角カナ濁点の結合は後続フェーズで別途対応する。
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from namemask.types import Span

# 辞書照合 fold 用のハイフン類（NFKC で吸収されないものを含む）。
# - (U+002D) ー(U+30FC) − (U+2212) ‐(U+2010) ―(U+2015) – — 〜 等を同一視。
_HYPHEN_CLASS = "-ー−‐―‒–—⁃－"
# 公開定数: 数字区切り（郵便番号・住所番地・電話）を扱う検出器が共有する
# ハイフン類の唯一の真実。NFKC は 2212/2010/30FC 等を '-' に吸収しないため、
# 各検出器の文字クラスはこの集合から生成すること（定義ドリフト防止）。
HYPHEN_CHARS: str = _HYPHEN_CLASS
_HYPHEN_CANON = "-"
_HYPHEN_TABLE = {ord(c): _HYPHEN_CANON for c in _HYPHEN_CLASS}
_HYPHEN_SET = set(_HYPHEN_CLASS)


def _nfkc_char(ch: str) -> str:
    return unicodedata.normalize("NFKC", ch)


@dataclass(frozen=True)
class NormalizedText:
    """原文と、その影テキスト＋charmap。

    charmap[j] は影テキスト j 文字目を生んだ原文の文字インデックス。
    charmap は非減少（原文を左から走査するため）。len(charmap)==len(shadow)。
    """

    original: str
    shadow: str
    charmap: tuple[int, ...]

    def to_original_offsets(self, s_start: int, s_end: int) -> tuple[int, int]:
        """影テキスト座標 [s_start, s_end) を原文座標へ逆変換する。

        展開元の原文文字を必ず丸ごと含める（原文文字は分割できない）。
        """
        if s_start < 0 or s_end > len(self.shadow) or s_end <= s_start:
            raise ValueError(
                f"invalid shadow span [{s_start}, {s_end}) for shadow len {len(self.shadow)}"
            )
        orig_start = self.charmap[s_start]
        orig_end = self.charmap[s_end - 1] + 1
        return orig_start, orig_end

    def map_span(self, span: Span) -> Span:
        """影テキスト座標の Span を原文座標の Span に変換する。"""
        start, end = self.to_original_offsets(span.start, span.end)
        return Span(
            start=start,
            end=end,
            type=span.type,
            score=span.score,
            sources=span.sources,
        )

    def map_spans(self, spans: list[Span]) -> list[Span]:
        return [self.map_span(s) for s in spans]


def normalize(text: str) -> NormalizedText:
    """原文を1文字ずつ NFKC 正規化し、影テキストと charmap を返す。"""
    shadow_parts: list[str] = []
    charmap: list[int] = []
    for i, ch in enumerate(text):
        norm = _nfkc_char(ch)
        for c in norm:  # 0 文字（消失）・複数文字（展開）いずれも追跡
            shadow_parts.append(c)
            charmap.append(i)
    return NormalizedText(
        original=text,
        shadow="".join(shadow_parts),
        charmap=tuple(charmap),
    )


def fold_normalize(text: str) -> NormalizedText:
    """辞書照合用の fold 済み第2影テキスト＋charmap。

    NFKC 影テキストに対し「空白除去」「ハイフン類の同一視」を施し、fold-charmap
    （fold影の各文字 -> 原文インデックス）を保持する。空白は「消える」ため
    charmap は 0 文字対応を含む（該当原文文字が fold影に現れない）。辞書層だけが
    この影の上で照合し、スパンは charmap で原文座標へ逆変換する。正規表現層・
    構造ルール層は空白・ハイフンが意味を持つため fold しない。
    """
    base = normalize(text)  # NFKC 影＋charmap を再利用
    parts: list[str] = []
    charmap: list[int] = []
    # shadow と charmap は normalize() が常に同じ長さで作る。ずれたら座標が壊れて
    # 検出漏れになるので、黙って切り捨てず strict で落とす。
    for ch, orig_i in zip(base.shadow, base.charmap, strict=True):
        if ch.isspace():
            continue  # 空白は除去（0 文字対応 = charmap に載せない）
        if ch in _HYPHEN_SET:
            parts.append(_HYPHEN_CANON)
            charmap.append(orig_i)
        else:
            parts.append(ch)
            charmap.append(orig_i)
    return NormalizedText(original=text, shadow="".join(parts), charmap=tuple(charmap))


def fold_for_dict(text: str) -> str:
    """辞書照合用の fold 文字列（座標なし。キー生成・比較専用）。

    fold_normalize と同一の変換規則。**辞書キー生成側にも同じ関数を適用して
    対称にする**こと（本文側・キー側で非対称だと取りこぼす）。
    """
    return fold_normalize(text).shadow
