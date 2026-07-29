"""NER 検出器の統合テスト（Planv2 §5.5 / §11 P4）。

GiNZA（ja_ginza）が利用可能な環境でのみ実行する。未導入なら module skip。
fail-safe テスト（bad model → []）は test_ner_failsafe.py で **常に** 実行する
（skip されては安全保証が無検証になるため、importorskip の外に置いている）。
"""

from __future__ import annotations

import pytest

pytest.importorskip("spacy", reason="spacy/ja_ginza 未導入")

from namemask.detectors.ner import NerDetector  # noqa: E402
from namemask.types import EntityType  # noqa: E402


def _load_or_skip() -> NerDetector:
    det = NerDetector()
    det._ensure_loaded()
    if det._nlp is None:
        pytest.skip("ja_ginza モデルをロードできない")
    return det


@pytest.fixture(scope="module")
def ner() -> NerDetector:
    return _load_or_skip()


def test_ner_detects_person_and_org(ner: NerDetector) -> None:
    spans = ner.detect("佐々木一郎が株式会社アオヤマ商事の窓口です。")
    types = {s.type for s in spans}
    assert EntityType.PERSON in types
    assert EntityType.ORGANIZATION in types


def test_ner_offsets_are_valid(ner: NerDetector) -> None:
    text = "佐々木一郎が株式会社アオヤマ商事の窓口です。"
    for s in ner.detect(text):
        assert 0 <= s.start < s.end <= len(text)
        assert text[s.start : s.end].strip() == text[s.start : s.end]  # 空白trim済み


def test_ner_location_filtered_by_default(ner: NerDetector) -> None:
    # enabled_types 既定は PERSON/ORGANIZATION のみ。LOCATION は emit しない。
    spans = ner.detect("私は東京都渋谷区に住んでいます。")
    assert all(s.type != EntityType.LOCATION for s in spans)
