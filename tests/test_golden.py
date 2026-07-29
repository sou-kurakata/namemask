"""golden 全ケースの round-trip（Planv2 §8.3 / §10）。

P1 のスタブ検出器（=正解スパン）を入力に、置換→復元が原文を完全復元し、
マスク後テキストに被マスク表記が残存しないことを全ケースで確認する。
"""

from __future__ import annotations

import pytest

from eval import Case
from namemask.core import mask, unmask
from namemask.detectors.stub import GoldenStubDetector
from namemask.types import Entity, EntityType


def _ids(cases: list[Case]) -> list[str]:
    return [c.id for c in cases]


def test_corpus_has_enough_cases(corpus: list[Case]) -> None:
    # §8.1 最低60ケース。
    assert len(corpus) >= 60


def test_roundtrip_all_cases(corpus: list[Case]) -> None:
    for case in corpus:
        spans = GoldenStubDetector(case.entities).detect(case.text)
        m = mask(case.text, spans)
        r = unmask(m.masked_text, m.mapping)
        assert r.text == case.text, f"[{case.id}] round-trip failed"
        assert not r.warnings, f"[{case.id}] unexpected warnings: {r.warnings}"


def test_no_masked_surface_remains(corpus: list[Case]) -> None:
    """マスク後テキストに被マスク文字列が残っていないこと（不変条件2）。

    nth 指定のケースは「同一表記の別出現が敢えて非エンティティ」（複合語内部の
    青葉 等）なので、その表記が本文に残るのは正しい。対象から除外する。
    """
    for case in corpus:
        if any(e.nth is not None for e in case.entities):
            continue
        spans = GoldenStubDetector(case.entities).detect(case.text)
        m = mask(case.text, spans)
        for item in m.report:
            assert item.original not in m.masked_text, (
                f"[{case.id}] surface {item.original!r} leaked into masked text"
            )


def test_same_surface_same_token(corpus: list[Case]) -> None:
    """同一表記が同一トークンに（文書内一貫性 §10）。"""
    for case in corpus:
        spans = GoldenStubDetector(case.entities).detect(case.text)
        m = mask(case.text, spans)
        # mapping は token->surface。異なる token が同じ surface を指さないこと。
        surfaces = list(m.mapping.values())
        assert len(surfaces) == len(set(surfaces)), (
            f"[{case.id}] same surface mapped to multiple tokens"
        )


def test_roundtrip_with_preexisting_canonical_placeholder() -> None:
    """原文に既存の正準プレースホルダがある場合の round-trip（回帰・経路1）。

    採番が既存の [[人名_1]] と衝突すると unmask の exact パスが原文側の
    [[人名_1]] まで置換して破壊する。番号スキップで根絶されること。
    """
    text = "設定は [[人名_1]] のままにしてください。山田さんへ連絡。"
    entities = [Entity("山田", EntityType.PERSON)]
    spans = GoldenStubDetector(entities).detect(text)
    m = mask(text, spans)
    # 既存文字列と衝突しない番号（_1 以外）が採番される
    assert "[[人名_1]]" not in m.mapping
    assert "[[人名_1]]" in m.masked_text  # 原文由来の文字列は不変
    r = unmask(m.masked_text, m.mapping)
    assert r.text == text


def test_roundtrip_with_preexisting_lenient_placeholder() -> None:
    """原文に既存の改変風プレースホルダがある場合の round-trip（回帰・経路2）。

    生成トークン [[人名_1]] の寛容パターンが原文の [人名 1] にマッチし、
    unmask の寛容パスが原文由来文字列を誤復元する。番号スキップで根絶。
    """
    text = "コード [人名 1] を確認。田中さんへ。"
    entities = [Entity("田中", EntityType.PERSON)]
    spans = GoldenStubDetector(entities).detect(text)
    m = mask(text, spans)
    assert "[[人名_1]]" not in m.mapping
    r = unmask(m.masked_text, m.mapping)
    assert r.text == text


@pytest.mark.parametrize(
    "mutator",
    [
        lambda t: t,                       # 無改変
        lambda t: t.replace("[[", "[").replace("]]", "]"),   # 角括弧1個
        lambda t: t.replace("[[", "【").replace("]]", "】"),  # 隅付き括弧
        lambda t: t.replace("_", " _"),                       # 空白混入
        lambda t: t.replace("_", " "),                        # アンダースコア脱落
    ],
)
def test_placeholder_mutation_restore(corpus: list[Case], mutator) -> None:
    """外部AIがプレースホルダを改変して返しても復元できる（§6.2）。"""
    for case in corpus:
        spans = GoldenStubDetector(case.entities).detect(case.text)
        if not spans:
            continue
        m = mask(case.text, spans)
        mutated = mutator(m.masked_text)
        r = unmask(mutated, m.mapping)
        assert r.text == case.text, (
            f"[{case.id}] failed to restore mutated placeholders: {mutated!r}"
        )
