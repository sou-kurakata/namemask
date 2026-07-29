"""置換エンジン — 可逆性。

不変条件:
- 双方向・可逆: 同一表記 -> 同一トークン、unmask(mask(x)) == x。
- 原文は書き換えない: 置換は原文座標に対し後方から前方へ適用。

このモジュールは検出精度から独立。入力スパンの正しさは呼び出し側の責任。
"""

from __future__ import annotations

from namemask.core.restorer import _lenient_pattern
from namemask.types import TYPE_LABEL_JA, MaskResult, ReportItem, Span


def _dedup_and_sort(spans: list[Span]) -> list[Span]:
    """重複除去して start 昇順に整列。重なりがあれば例外（統合層の責務違反）。

    置換エンジンは「クリーンな非重複スパン」を前提とする。
    重複マージは統合層の仕事であり、ここで内部で処理すると
    座標バグを隠蔽するため、明示的に落とす。
    """
    # 完全一致は許容（同じスパンが複数層から来ることは正常）
    uniq: list[Span] = []
    seen: set[tuple[int, int, str]] = set()
    for s in spans:
        key = (s.start, s.end, s.type)
        if key not in seen:
            seen.add(key)
            uniq.append(s)

    ordered = sorted(uniq, key=lambda s: (s.start, s.end))
    for prev, cur in zip(ordered, ordered[1:]):
        if cur.start < prev.end:
            raise ValueError(
                f"overlapping spans passed to replacer: {prev} vs {cur}. "
                "Merge them in the span-merger layer first (Planv2 §5.6)."
            )
    return ordered


def _placeholder(type_: str, index: int) -> str:
    label = TYPE_LABEL_JA[type_]
    return f"[[{label}_{index}]]"


def mask(text: str, spans: list[Span]) -> MaskResult:
    """spans をプレースホルダに置換し、mapping と report を返す。

    - 同一表記（surface 文字列が同一）は同一トークンに割り当てる。
    - トークン採番は型ごとに、本文の初出順（start 昇順）で 1 から。
    - 置換は後方スパンから前方へ適用し座標ずれを防ぐ。
    """
    ordered = _dedup_and_sort(spans)

    # 型ごとの採番カウンタと、surface -> token の対応
    counters: dict[str, int] = {}
    surface_to_token: dict[tuple[str, str], str] = {}
    mapping: dict[str, str] = {}
    report: list[ReportItem] = []

    # 初出順（start 昇順）でトークンを確定
    for span in ordered:
        surface = span.surface(text)
        key = (span.type, surface)
        if key not in surface_to_token:
            label = TYPE_LABEL_JA[span.type]
            index = counters.get(span.type, 0) + 1
            # 原文に既存のプレースホルダ風文字列（正準形・改変形いずれも）と
            # 衝突する番号はスキップする（欠番許容）。寛容パターンは正準形を
            # 包含するため、これ1つで unmask 時の (1) 二重置換・(2) 原文由来
            # 文字列の誤復元 の両経路を根絶する。
            while _lenient_pattern(label, index).search(text):
                index += 1
            counters[span.type] = index
            token = _placeholder(span.type, index)
            surface_to_token[key] = token
            mapping[token] = surface
            report.append(
                ReportItem(
                    original=surface,
                    token=token,
                    type=span.type,
                    sources=span.sources,
                )
            )

    # 置換は後方から（start 降順）
    chars = text
    for span in sorted(ordered, key=lambda s: s.start, reverse=True):
        surface = chars[span.start : span.end]
        token = surface_to_token[(span.type, surface)]
        chars = chars[: span.start] + token + chars[span.end :]

    return MaskResult(masked_text=chars, mapping=mapping, report=report)
