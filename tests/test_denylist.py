"""辞書層のテスト（Planv2 §5.4）。"""

from __future__ import annotations

from namemask.detectors.denylist import (
    ClientRow,
    DenylistDetector,
    expand_variants,
    load_clients_csv,
)
from namemask.types import EntityType


def test_expand_variants_core_and_forms() -> None:
    row = ClientRow("株式会社アオヤマ商事", EntityType.ORGANIZATION, ["アオヤマ"])
    v = expand_variants(row, min_core_len=3)
    assert "株式会社アオヤマ商事" in v      # 原表記
    assert "アオヤマ商事" in v              # コア名
    assert "アオヤマ商事株式会社" in v      # 後置
    assert "(株)アオヤマ商事" in v          # 別法人格前置
    assert "アオヤマ" in v                  # alias


def test_expand_variants_short_core_not_registered_alone() -> None:
    # コア名が2文字以下のときはコア単体を登録しない（安全弁）。
    row = ClientRow("株式会社AB", EntityType.ORGANIZATION, [])
    v = expand_variants(row, min_core_len=3)
    assert "AB" not in v
    # 法人格付きは残る
    assert "株式会社AB" in v
    assert "(株)AB" in v


def test_denylist_detects_core_name() -> None:
    rows = [ClientRow("株式会社アオヤマ商事", EntityType.ORGANIZATION, ["アオヤマ"])]
    det = DenylistDetector(rows, min_core_len=3)
    text = "アオヤマ商事の追加発注について"
    got = [(s.type, text[s.start : s.end]) for s in det.detect_shadow(text)]
    assert (EntityType.ORGANIZATION, "アオヤマ商事") in got


def test_denylist_detects_alias_and_fullform() -> None:
    rows = [ClientRow("合同会社サクラソフトウェア", EntityType.ORGANIZATION, ["サクラソフト"])]
    det = DenylistDetector(rows, min_core_len=3)
    for text, surface in [
        ("合同会社サクラソフトウェアより", "合同会社サクラソフトウェア"),
        ("サクラソフトに依頼", "サクラソフト"),
        ("サクラソフトウェアのレポート", "サクラソフトウェア"),
    ]:
        got = [text[s.start : s.end] for s in det.detect_shadow(text)]
        assert surface in got, (text, got)


def test_expand_variants_are_folded() -> None:
    # 長音ー を含む名称のキーは fold で '-' に正規化される（ADR-007 対称性）。
    row = ClientRow("株式会社スカイーテック", EntityType.ORGANIZATION, [])
    v = expand_variants(row, min_core_len=3)
    assert "スカイ-テック" in v  # コア名 fold 済み
    assert "スカイーテック" not in v  # 生の長音表記はキーに残さない


def test_denylist_hyphen_and_space_variants_via_fold() -> None:
    """P3.5-1: 別ハイフン種・空白挿入も fold 影で拾う（FoldNormalizingDetector 経由）。"""
    from namemask.detectors.normalizing import FoldNormalizingDetector

    rows = [ClientRow("株式会社スカイーテック", EntityType.ORGANIZATION, ["スカイテック"])]
    det = FoldNormalizingDetector(DenylistDetector(rows, min_core_len=3))
    for text, surface in [
        ("スカイ−テックへ発注", "スカイ−テック"),      # U+2212 マイナス
        ("スカイ‐テックと契約", "スカイ‐テック"),      # U+2010 ハイフン
        ("スカイ テックに連絡", "スカイ テック"),        # 半角空白（alias 経由）
    ]:
        got = [text[s.start : s.end] for s in det.detect(text)]
        assert surface in got, (text, got)


def test_load_clients_csv(clients_csv: str) -> None:
    rows = load_clients_csv(clients_csv)
    names = {r.name for r in rows}
    assert "株式会社アオヤマ商事" in names
    assert all(r.type == EntityType.ORGANIZATION for r in rows)
