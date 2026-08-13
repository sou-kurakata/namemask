"""スパン統合層のテスト（Planv2 §5.6）。"""

from __future__ import annotations

from itertools import pairwise

from namemask.pipeline.merger import merge_spans
from namemask.types import EntityType, Span


def _no_overlaps(spans: list[Span]) -> bool:
    ordered = sorted(spans, key=lambda s: s.start)
    return all(a.end <= b.start for a, b in pairwise(ordered))


def test_overlap_merge_widest_and_type_priority() -> None:
    text = "山田商事"
    # 辞書 ORG(0-4) と NER PERSON(0-2) が重なる → 最広(0-4)・型は辞書優先で ORG
    spans = [
        Span(0, 4, EntityType.ORGANIZATION, sources=("denylist",)),
        Span(0, 2, EntityType.PERSON, sources=("ner",)),
    ]
    merged = merge_spans(text, spans)
    assert len(merged) == 1
    assert (merged[0].start, merged[0].end) == (0, 4)
    assert merged[0].type == EntityType.ORGANIZATION


def test_org_boundary_expansion_absorbs_legal_form() -> None:
    text = "アオヤマ商事株式会社の件"
    # 辞書がコア名だけ拾った状態 → 直後の法人格を取り込む
    spans = [Span(0, 6, EntityType.ORGANIZATION, sources=("denylist",))]
    merged = merge_spans(text, spans)
    assert len(merged) == 1
    assert text[merged[0].start : merged[0].end] == "アオヤマ商事株式会社"


def test_same_surface_propagation() -> None:
    text = "アオヤマ商事とアオヤマ商事は別法人"
    spans = [Span(0, 6, EntityType.ORGANIZATION, sources=("denylist",))]
    merged = merge_spans(text, spans)
    surfaces = [text[s.start : s.end] for s in merged]
    assert surfaces.count("アオヤマ商事") == 2
    assert all("propagation" in s.sources or "denylist" in s.sources for s in merged)


def test_output_is_non_overlapping() -> None:
    text = "株式会社アオヤマ商事の山田様"
    spans = [
        Span(0, 10, EntityType.ORGANIZATION, sources=("structural",)),
        Span(4, 10, EntityType.ORGANIZATION, sources=("denylist",)),
        Span(11, 13, EntityType.PERSON, sources=("structural",)),
    ]
    merged = merge_spans(text, spans)
    assert _no_overlaps(merged)


def test_propagation_does_not_enter_compound_word() -> None:
    # P3.5-3: 青葉様 検出後、青葉区役所 内部の 青葉 へ伝播しない。
    text = "青葉様より、青葉区役所への申請"
    spans = [Span(0, 2, EntityType.PERSON, sources=("structural",))]  # 先頭の青葉
    merged = merge_spans(text, spans)
    second = text.find("青葉", 2)
    assert all(not (s.start <= second < s.end) for s in merged)
    assert sum(text[s.start : s.end] == "青葉" for s in merged) == 1


def test_propagation_reexpansion_absorbs_prefix_legal_form() -> None:
    # P3.5-3: 伝播で生じた ORG にも境界拡張が効く（拡張→マージ→伝播→拡張→マージ）。
    # 前置 (株) は '(' が名称連続文字でないため伝播ガードに阻まれず、伝播後の
    # 再拡張で法人格を取り込める（後置 株式会社 は 株 が名称連続のため伝播対象外）。
    text = "アオヤマ商事の件。(株)アオヤマ商事へ発注。"
    spans = [Span(0, 6, EntityType.ORGANIZATION, sources=("denylist",))]
    merged = merge_spans(text, spans)
    surfaces = {text[s.start : s.end] for s in merged}
    assert "(株)アオヤマ商事" in surfaces


def test_empty() -> None:
    assert merge_spans("何もない", []) == []


# ---- ORG コア名伝播（2026-07 P7後レビュー修正 1）----


def test_core_name_propagation_for_structural_org() -> None:
    # 辞書外の取引先: 「株式会社◯◯ … ◯◯」の法人格なし再言及を伝播で拾う。
    text = "株式会社アオゾラ商事の件で打合せ。アオゾラ商事の担当者は不在。"
    spans = [Span(0, 10, EntityType.ORGANIZATION, sources=("structural",))]
    merged = merge_spans(text, spans)
    second = text.find("アオゾラ商事", 10)
    hit = [s for s in merged if s.start == second]
    assert hit, f"bare core name not propagated: {merged}"
    assert hit[0].type == EntityType.ORGANIZATION
    assert "propagation" in hit[0].sources


def test_core_name_propagation_suffix_legal_form() -> None:
    # 後置法人格（◯◯株式会社）でもコア名を剥がして伝播する。
    text = "ミナヅキ工業株式会社と契約。窓口はミナヅキ工業です。"
    spans = [Span(0, 10, EntityType.ORGANIZATION, sources=("structural",))]
    merged = merge_spans(text, spans)
    second = text.find("ミナヅキ工業", 10)
    assert any(s.start == second for s in merged), merged


def test_core_name_propagation_respects_compound_guard() -> None:
    # コア名の伝播も複合語境界ガードに従う（◯◯ビル 内部へ食い込まない）。
    text = "株式会社ハクバ商事に連絡。会場はハクバ商事ビルの3階。"
    spans = [Span(0, 9, EntityType.ORGANIZATION, sources=("structural",))]
    merged = merge_spans(text, spans)
    second = text.find("ハクバ商事", 9)
    assert all(not (s.start <= second < s.end) for s in merged), merged


def test_propagation_matches_fullwidth_variant_via_shadow() -> None:
    # 伝播は NFKC 影上で照合するため、全角バリアント（ＡＣＭＥ↔ACME）へも効く。
    text = "ACME株式会社と契約。追ってＡＣＭＥから請求書が届く。"
    spans = [Span(0, 8, EntityType.ORGANIZATION, sources=("structural",))]  # ACME株式会社
    merged = merge_spans(text, spans)
    fw = text.find("ＡＣＭＥ")
    hit = [s for s in merged if s.start == fw]
    assert hit, f"full-width variant not propagated: {merged}"
    assert text[hit[0].start : hit[0].end] == "ＡＣＭＥ"
    assert hit[0].type == EntityType.ORGANIZATION
    assert "propagation" in hit[0].sources


def test_core_name_propagation_min_length_guard() -> None:
    # コア名が3文字未満（誤マッチ多発帯）は伝播しない（§5.4 安全弁と同じ閾値）。
    text = "株式会社丸和を訪問。丸和の担当は明日戻ります。"
    spans = [Span(0, 6, EntityType.ORGANIZATION, sources=("structural",))]
    merged = merge_spans(text, spans)
    second = text.find("丸和", 6)
    assert all(s.start != second for s in merged), merged
