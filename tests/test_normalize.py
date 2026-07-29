"""正規化層のテスト（Planv2 §5.1 / §11 P2）。

- charmap の不変条件（長さ・非減少・範囲）
- 影テキスト座標 -> 原文座標の逆変換の正しさ
- 全角/㈱ ケースが「正規化で検出可能になる」ことの eval 確認
- fold_for_dict の対称性（本文側・キー側で同一結果）
"""

from __future__ import annotations

import unicodedata

from hypothesis import given, settings
from hypothesis import strategies as st

from eval import Case
from namemask.core import mask, unmask
from namemask.detectors import NormalizingDetector
from namemask.normalize import fold_for_dict, fold_normalize, normalize
from namemask.types import EntityType, Span


def _nfkc_each(s: str) -> str:
    """影テキストと同じ「1文字ずつ NFKC」で文字列を正規化する。"""
    return "".join(unicodedata.normalize("NFKC", ch) for ch in s)


# ---- charmap の基本性質 ----

def test_charmap_basic_invariants() -> None:
    for text in ["", "abc", "㈱アオヤマ商事", "０３－１２３４", "ｉｎｆｏ＠ｅｘ．ｃｏｍ"]:
        norm = normalize(text)
        assert len(norm.charmap) == len(norm.shadow)
        # 非減少
        assert all(a <= b for a, b in zip(norm.charmap, norm.charmap[1:]))
        # 範囲内
        assert all(0 <= i < max(1, len(text)) for i in norm.charmap) or text == ""


def test_glyph_expansion_charmap() -> None:
    norm = normalize("㈱X")
    # ㈱ -> (株) の 1->3 展開、X はそのまま
    assert norm.shadow == "(株)X"
    assert norm.charmap == (0, 0, 0, 1)


def test_fullwidth_digits_map_one_to_one() -> None:
    norm = normalize("０３")
    assert norm.shadow == "03"
    assert norm.charmap == (0, 1)


# ---- スパン逆変換 ----

def test_map_span_within_expansion_covers_whole_source_char() -> None:
    norm = normalize("A㈱B")  # shadow = "A(株)B", charmap=(0,1,1,1,2)
    assert norm.shadow == "A(株)B"
    # 影テキストで "株" だけ（部分）にマッチしても、原文では ㈱ 全体を指す
    s = norm.shadow.index("株")
    span = norm.map_span(Span(s, s + 1, "ORGANIZATION"))
    assert norm.original[span.start : span.end] == "㈱"


def test_map_span_multichar_expansion_full() -> None:
    norm = normalize("㈱アオヤマ")  # shadow = "(株)アオヤマ"
    nf = _nfkc_each("㈱アオヤマ")
    s = norm.shadow.index(nf)
    span = norm.map_span(Span(s, s + len(nf), "ORGANIZATION"))
    assert norm.original[span.start : span.end] == "㈱アオヤマ"


# ---- eval 確認: 全角/㈱ ケースが正規化で検出可能になる ----

def test_fullwidth_cases_become_detectable_via_normalization(corpus: list[Case]) -> None:
    """P2 完了条件（§11）: 正規化しないと素通りする全角系が、影テキスト上で
    検出可能になり、逆変換で原文の該当表記に正確に戻ることを全ケースで確認。
    """
    checked = 0
    for case in corpus:
        # propagation-variant は「半角と全角が同一本文に共存」する伝播用ケースで、
        # 正規化形が原文の別位置にも現れる（P2 検出可能性の前提と異なる）ため除外。
        if case.category == "propagation-variant":
            continue
        norm = normalize(case.text)
        for ent in case.entities:
            query = _nfkc_each(ent.surface)
            if query == ent.surface:
                continue  # 正規化で変化しない（半角）ケースは対象外
            checked += 1
            # 正規化前は素通り（原文には正規化形が現れない）
            assert query not in case.text, (
                f"[{case.id}] raw text unexpectedly contains normalized form"
            )
            # 影テキスト上では検出可能
            assert query in norm.shadow, f"[{case.id}] not detectable on shadow"
            # 逆変換で原文の該当表記に正確に戻る
            s = norm.shadow.index(query)
            span = norm.map_span(Span(s, s + len(query), ent.type))
            assert case.text[span.start : span.end] == ent.surface, (
                f"[{case.id}] span mapped back to {case.text[span.start:span.end]!r}, "
                f"expected {ent.surface!r}"
            )
    # 全角系ケースが実際に存在し、検査が空回りしていないこと
    assert checked >= 10, f"only {checked} full-width entities exercised"


def test_normalized_detection_roundtrips(corpus: list[Case]) -> None:
    """影テキストで拾って逆変換したスパンで mask->unmask しても round-trip する。"""
    for case in corpus:
        norm = normalize(case.text)
        spans = []
        consumed = [False] * len(case.text)
        for ent in case.entities:
            query = _nfkc_each(ent.surface)
            start = norm.shadow.find(query)
            if start == -1:
                continue
            span = norm.map_span(Span(start, start + len(query), ent.type))
            if any(consumed[span.start : span.end]):
                continue
            for i in range(span.start, span.end):
                consumed[i] = True
            spans.append(span)
        m = mask(case.text, spans)
        r = unmask(m.masked_text, m.mapping)
        assert r.text == case.text, f"[{case.id}] round-trip failed"


# ---- NormalizingDetector アダプタ ----

def test_normalizing_detector_adapter() -> None:
    """影テキスト検出器を原文座標検出器に昇格できる。"""

    class _FullwidthDigitRun:
        name = "toy"

        def detect_shadow(self, shadow: str) -> list[Span]:
            import re
            return [
                Span(m.start(), m.end(), "PHONE", sources=(self.name,))
                for m in re.finditer(r"\d{2,}", shadow)
            ]

    det = NormalizingDetector(_FullwidthDigitRun())
    text = "番号は０３１２３４"  # 全角数字。原文では \d に半角前提だと当たらない
    spans = det.detect(text)
    assert len(spans) == 1
    assert text[spans[0].start : spans[0].end] == "０３１２３４"


# ---- fold_for_dict の対称性 ----

def test_fold_for_dict_symmetry_hyphen_and_space() -> None:
    # 本文側の全角/ハイフン種/空白の揺れが、キー側の素直な表記と一致する
    assert fold_for_dict("０３ー１２３４−５６７８") == fold_for_dict("03-1234-5678")
    assert fold_for_dict("ＡＢＣ 商事") == fold_for_dict("ABC商事")
    assert fold_for_dict("東京　工業‐所") == fold_for_dict("東京工業-所")


# ---- fold 影テキスト（ADR-007）----

def test_fold_normalize_charmap_maps_back_over_removed_space() -> None:
    # 空白は消え、ハイフン類は '-' に。charmap は原文座標へ正しく戻る。
    norm = fold_normalize("アオヤマ　商事")  # 全角空白
    assert norm.shadow == "アオヤマ商事"
    s = norm.shadow.index("アオヤマ商事")
    span = norm.map_span(Span(s, s + len("アオヤマ商事"), EntityType.ORGANIZATION))
    # 逆変換すると原文の空白を含む範囲（アオヤマ　商事）を覆う
    assert norm.original[span.start : span.end] == "アオヤマ　商事"


def test_fold_normalize_unifies_hyphen_variants() -> None:
    for raw in ["スカイ−テック", "スカイ‐テック", "スカイーテック", "スカイ―テック"]:
        assert fold_normalize(raw).shadow == "スカイ-テック"


def test_fold_for_dict_matches_fold_normalize_shadow() -> None:
    for s in ["", "アオヤマ　商事", "スカイ−テック", "03ー1234", "普通のテキスト"]:
        assert fold_for_dict(s) == fold_normalize(s).shadow


@settings(max_examples=200)
@given(st.text(max_size=60))
def test_fold_charmap_property(text: str) -> None:
    norm = fold_normalize(text)
    assert len(norm.charmap) == len(norm.shadow)
    prev = -1
    for i in norm.charmap:
        assert prev <= i < len(text)
        prev = i


@settings(max_examples=300)
@given(st.text(max_size=60))
def test_charmap_property(text: str) -> None:
    norm = normalize(text)
    assert len(norm.charmap) == len(norm.shadow)
    # 非減少かつ範囲内
    prev = -1
    for i in norm.charmap:
        assert prev <= i < len(text)
        prev = i
    # 任意の影スパンは原文の妥当な範囲に戻る
    if norm.shadow:
        span = norm.map_span(Span(0, len(norm.shadow), "PERSON"))
        assert 0 <= span.start < span.end <= len(text)
