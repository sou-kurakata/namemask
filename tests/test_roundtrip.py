"""Property-based round-trip テスト（Planv2 §8.3）。

ランダム日本語混じりテキスト＋ランダム検出スパンに対し、座標処理の
オフバイワンや置換順序バグを大量試行で炙り出す。
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from namemask.core import mask, unmask
from namemask.detectors.stub import GoldenStubDetector
from namemask.types import ALL_TYPES, Entity

# 「原文に既にプレースホルダ風文字列が含まれる」バグ類をhypothesisが探索
# できるよう、括弧・アンダースコア・数字・ラベル文字を敢えて含める。
_ALPHABET = (
    "あいうえおかきくけこさしすせそたちつてとなにぬねの"
    "アイウエオカキクケコサシスセソ・ー"
    "山田佐藤鈴木高橋商事工業株式会社"
    "人名組織メール電話マイナンバー地名"  # プレースホルダ・ラベル文字
    "[]【】_"                              # 括弧・アンダースコア（プレースホルダ風生成）
    "abcXYZ0123456789 @.-"
    "\n"
)


@st.composite
def text_and_entities(draw):
    text = draw(st.text(alphabet=_ALPHABET, min_size=0, max_size=160))
    entities: list[Entity] = []
    if text:
        k = draw(st.integers(min_value=0, max_value=4))
        for _ in range(k):
            start = draw(st.integers(min_value=0, max_value=len(text) - 1))
            length = draw(st.integers(min_value=1, max_value=min(8, len(text) - start)))
            surface = text[start : start + length]
            type_ = draw(st.sampled_from(ALL_TYPES))
            entities.append(Entity(surface=surface, type=type_))
    return text, entities


@settings(max_examples=400)
@given(text_and_entities())
def test_roundtrip_property(data) -> None:
    text, entities = data
    # スタブは全出現を非重複で拾う（同一表記伝播の理想形）。
    spans = GoldenStubDetector(entities).detect(text)
    m = mask(text, spans)
    r = unmask(m.masked_text, m.mapping)
    assert r.text == text


@settings(max_examples=400)
@given(text_and_entities())
def test_no_masked_surface_remains_property(data) -> None:
    text, entities = data
    spans = GoldenStubDetector(entities).detect(text)
    m = mask(text, spans)
    # 挿入したトークン内部の文字（採番の数字や日本語ラベル）は「残存」に数えない。
    # 例: surface="1" は [[人名_1]] の数字と衝突するが漏洩ではない。
    # 全トークンをセンチネルに潰した残りテキストに被マスク表記が無いことを確認。
    stripped = m.masked_text
    for token in m.mapping:
        stripped = stripped.replace(token, "\x00")
    for item in m.report:
        assert item.original not in stripped


@settings(max_examples=400)
@given(text_and_entities())
def test_stub_spans_non_overlapping(data) -> None:
    text, entities = data
    spans = GoldenStubDetector(entities).detect(text)
    ordered = sorted(spans, key=lambda s: s.start)
    for a, b in zip(ordered, ordered[1:]):
        assert a.end <= b.start, f"overlapping spans: {a} {b}"
