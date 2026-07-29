"""構造ルール層のテスト（Planv2 §5.3）。"""

from __future__ import annotations

from namemask.detectors.structural_ja import StructuralDetector
from namemask.types import EntityType


def _detect(text: str) -> list[tuple[str, str]]:
    det = StructuralDetector()
    return [(s.type, text[s.start : s.end]) for s in det.detect_shadow(text)]


def test_org_prefix_and_suffix() -> None:
    assert (EntityType.ORGANIZATION, "株式会社アオヤマ商事") in _detect(
        "株式会社アオヤマ商事の件"
    )
    assert (EntityType.ORGANIZATION, "ツバサ工業株式会社") in _detect(
        "本日、ツバサ工業株式会社へ発注"
    )


def test_org_abbrev_paren_form_on_shadow() -> None:
    # 影テキストでは (株) 形（㈱/（株）は §5.1 が正規化）。
    assert (EntityType.ORGANIZATION, "(株)キリシマ電機") in _detect(
        "(株)キリシマ電機の田中"
    )


def test_org_keigo_name_only() -> None:
    # 御中 の直前は組織候補。スパンは名称部のみ（御中を含めない）。
    got = _detect("アオヤマ商事御中")
    assert (EntityType.ORGANIZATION, "アオヤマ商事") in got
    assert all(g[1] != "アオヤマ商事御中" for g in got)


def test_person_honorific_and_role() -> None:
    assert (EntityType.PERSON, "山田") in _detect("山田様より連絡")
    assert (EntityType.PERSON, "佐藤") in _detect("佐藤課長の承認")
    assert (EntityType.PERSON, "アンナ") in _detect("アンナ様からの質問")


def test_person_span_excludes_honorific() -> None:
    got = _detect("高橋主任が同席")
    assert (EntityType.PERSON, "高橋") in got
    assert all("主任" not in g[1] for g in got)


def test_person_stopwords_excluded() -> None:
    assert _detect("皆さん、ありがとう") == []
    assert _detect("お客様各位") == []
    assert _detect("奥様によろしく") == []


def test_person_dept_left_boundary_guard() -> None:
    # P3.5-2: 部署名の食い込みを是正し、人名だけを拾う。
    assert (EntityType.PERSON, "田中") in _detect("営業部田中様より連絡")
    assert all("業部" not in surf for _, surf in _detect("営業部田中様より連絡"))
    assert (EntityType.PERSON, "高橋") in _detect("経理部高橋主任が対応")


def test_person_name_with_repetition_mark() -> None:
    # 繰返し記号 々(U+3005) を含む姓（佐々木）が「木」だけにならず全体を拾う。
    assert (EntityType.PERSON, "佐々木") in _detect("佐々木様より連絡")
    assert (EntityType.PERSON, "佐々木") in _detect("佐々木課長に確認します")
    assert all(surf != "木" for _, surf in _detect("佐々木様より連絡"))


def test_person_general_word_excluded() -> None:
    # P3.5-2: 一般語（担当者/関係者）は人名として拾わない。
    assert _detect("ご担当者様、お世話に") == []
    assert _detect("関係者各位へ") == []


def test_org_institution_explanation_not_matched() -> None:
    # 「株式会社とは…」の制度説明は誤検出しない（直後がひらがなで停止）。
    assert _detect("株式会社とは、株式を発行する会社形態です") == []
