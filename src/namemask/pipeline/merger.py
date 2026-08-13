"""スパン統合層。

全検出層のスパン（原文座標）を受け取り、順に:
  1. 境界拡張   … ORG に隣接する法人格を取り込む
  2. 重複マージ … 重なるスパンを最広範囲へ統合
  3. 型解決     … 辞書 > 構造 > 正規表現 > NER の優先度
  4. 同一表記伝播 … 検出済み表記の未検出な同一表記を全部拾う
出力は原文座標の非重複スパン（置換エンジンの前提を満たす）。
"""

from __future__ import annotations

import re

from namemask.lexicon import LEGAL_FORMS, NAME_CONTINUATION_CLASS, strip_legal_form
from namemask.normalize import normalize
from namemask.types import SOURCE_PRIORITY, EntityType, Span

# 同一表記伝播で拾う最小表記長（過剰伝播の暴発防止）。
_MIN_PROPAGATE_LEN = 2

# ORG コア名（法人格を剥がした名称）を伝播させる最小長。
# 辞書層の min_core_len 既定（2文字以下は登録しない）と同じ安全弁。
_MIN_CORE_PROPAGATE_LEN = 3

# 伝播先の前後がこのクラスの文字なら複合語内部とみなし伝播しない。
_NAME_CONT_RE = re.compile(f"[{NAME_CONTINUATION_CLASS}]")


def _is_name_continuation(ch: str) -> bool:
    return bool(ch) and _NAME_CONT_RE.match(ch) is not None


def _span_priority(span: Span) -> int:
    if not span.sources:
        return 0
    return max(SOURCE_PRIORITY.get(s, 0) for s in span.sources)


def _expand_org_boundaries(text: str, spans: list[Span]) -> list[Span]:
    """ORG スパンに隣接する法人格文字列を取り込む。

    元スパンは残し、拡張版を追加する（重複マージで最広が採用される）。
    PERSON 直後の敬称は取り込まない（PERSON はここでは対象外）。
    """
    extra: list[Span] = []
    for s in spans:
        if s.type != EntityType.ORGANIZATION:
            continue
        new_start, new_end = s.start, s.end
        for lf in LEGAL_FORMS:
            # 直後に後置法人格
            if text[s.end : s.end + len(lf)] == lf:
                new_end = max(new_end, s.end + len(lf))
            # 直前に前置法人格
            if s.start - len(lf) >= 0 and text[s.start - len(lf) : s.start] == lf:
                new_start = min(new_start, s.start - len(lf))
        if (new_start, new_end) != (s.start, s.end):
            extra.append(
                Span(new_start, new_end, s.type, score=s.score,
                     sources=(*tuple(s.sources), "boundary"))
            )
    return spans + extra


def _merge_overlaps(spans: list[Span]) -> list[Span]:
    """重なるスパンを最広範囲へ統合し、型を優先度で解決する。"""
    if not spans:
        return []
    ordered = sorted(spans, key=lambda s: (s.start, -s.end))
    clusters: list[list[Span]] = [[ordered[0]]]
    cur_end = ordered[0].end
    for s in ordered[1:]:
        if s.start < cur_end:  # 重なり（隣接=接触は含めない）
            clusters[-1].append(s)
            cur_end = max(cur_end, s.end)
        else:
            clusters.append([s])
            cur_end = s.end

    merged: list[Span] = []
    for cluster in clusters:
        start = min(c.start for c in cluster)
        end = max(c.end for c in cluster)
        # 型解決: 優先度（辞書>構造>正規表現>NER）→ 同点はより長いスパン。
        winner = max(cluster, key=lambda c: (_span_priority(c), c.end - c.start))
        sources: tuple[str, ...] = tuple(
            dict.fromkeys(src for c in cluster for src in c.sources)
        )
        merged.append(
            Span(start, end, winner.type,
                 score=max(c.score for c in cluster), sources=sources)
        )
    return merged


def _propagation_candidates(
    text: str, spans: list[Span]
) -> list[tuple[str, str, float, tuple[str, ...]]]:
    """伝播対象の (表記, 型, score, sources) 候補を列挙する。

    通常の同一表記に加え、ORGANIZATION は法人格を剥がしたコア名も候補にする
    （「本文では法人格抜きが最頻」の帰結。辞書外の取引先が
    「株式会社◯◯ … ◯◯」と再言及されるケースの取りこぼしを塞ぐ）。
    コア名は _MIN_CORE_PROPAGATE_LEN 未満なら候補にしない（誤マッチ安全弁）。
    過剰側に倒れる分は recall 優先で許容（人間レビューで捨てられる）。
    """
    cands: list[tuple[str, str, float, tuple[str, ...]]] = []
    seen: set[tuple[str, str]] = set()
    for s in spans:
        surface = text[s.start : s.end]
        variants = [surface]
        if s.type == EntityType.ORGANIZATION:
            lf, core = strip_legal_form(surface)
            if lf and len(core) >= _MIN_CORE_PROPAGATE_LEN:
                variants.append(core)
        for v in variants:
            if len(v) < _MIN_PROPAGATE_LEN:
                continue
            key = (v, s.type)
            if key not in seen:
                seen.add(key)
                cands.append((v, s.type, s.score, tuple(s.sources)))
    return cands


def _propagate_same_surface(text: str, spans: list[Span]) -> list[Span]:
    """検出済み表記（＋ORGコア名）を本文の他位置でも拾う。

    伝播は **NFKC 影テキスト上** で照合する。原文座標で raw 比較すると、NFKC で
    同一視される表記揺れ（全角英数 ＡＣＭＥ↔ACME、㈱↔(株) 等）が素通りするため
    （辞書層は fold 影で拾えるが、構造ルール/NER 起点の未知組織はこの穴に落ちる）。
    見つけたスパンは charmap で原文座標へ逆変換する。境界ガードも影側で判定して
    一貫させる。
    """
    norm = normalize(text)
    shadow = norm.shadow

    # 既存スパンのカバー範囲を影座標へ写す（影char -> 原文index -> 被覆判定）。
    covered_orig = bytearray(len(text))
    for s in spans:
        for i in range(s.start, s.end):
            covered_orig[i] = 1
    covered_shadow = bytearray(
        covered_orig[norm.charmap[j]] for j in range(len(shadow))
    )

    # 候補表記を影形へ正規化してから、長い順に伝播（部分表記の暴発を抑える）。
    norm_cands: list[tuple[str, str, float, tuple[str, ...]]] = []
    seen: set[tuple[str, str]] = set()
    for surface, typ, score, sources in _propagation_candidates(text, spans):
        q = normalize(surface).shadow
        if len(q) < _MIN_PROPAGATE_LEN:
            continue
        key = (q, typ)
        if key in seen:
            continue
        seen.add(key)
        norm_cands.append((q, typ, score, sources))

    additions: list[Span] = []
    for q, typ, score, sources in sorted(norm_cands, key=lambda c: len(c[0]), reverse=True):
        idx = shadow.find(q)
        qlen = len(q)
        while idx != -1:
            end = idx + qlen
            # 境界ガード（影側）: 前後が名称連続文字なら複合語内部とみなし伝播しない。
            before = shadow[idx - 1] if idx > 0 else ""
            after = shadow[end] if end < len(shadow) else ""
            if (
                not any(covered_shadow[idx:end])
                and not _is_name_continuation(before)
                and not _is_name_continuation(after)
            ):
                o_start, o_end = norm.to_original_offsets(idx, end)
                for j in range(idx, end):
                    covered_shadow[j] = 1
                additions.append(
                    Span(o_start, o_end, typ, score=score,
                         sources=(*sources, "propagation"))
                )
            idx = shadow.find(q, idx + 1)
    return spans + additions


def merge_spans(text: str, spans: list[Span]) -> list[Span]:
    """検出スパン集合を非重複の確定スパンへ統合する。"""
    if not spans:
        return []
    # 適用順序: 拡張 → マージ → 伝播 → 拡張 → マージ。
    # 伝播で新規に生じた ORG スパンにも境界拡張が効くよう、伝播後に再度拡張する。
    spans = _expand_org_boundaries(text, spans)
    spans = _merge_overlaps(spans)
    spans = _propagate_same_surface(text, spans)
    spans = _expand_org_boundaries(text, spans)
    spans = _merge_overlaps(spans)
    spans.sort(key=lambda s: (s.start, s.end))
    return spans
