"""住所検出のテスト（Planv2 §11 P7）。"""

from __future__ import annotations

from eval import Case, evaluate
from namemask.config import Config
from namemask.core import mask, unmask
from namemask.detectors.address_ja import AddressDetector
from namemask.pipeline.build import make_pipeline
from namemask.types import EntityType


def _detect(text: str) -> list[tuple[str, str]]:
    return [(s.type, text[s.start:s.end]) for s in AddressDetector().detect_shadow(text)]


def test_postal_and_prefecture_address_detected() -> None:
    got = _detect("〒150-0001 東京都渋谷区神宮前一丁目2番3号")
    assert (EntityType.ADDRESS, "〒150-0001") in got
    assert (EntityType.ADDRESS, "東京都渋谷区神宮前一丁目2番3号") in got


def test_bare_place_names_not_detected() -> None:
    # 単独地名・単独県名は対象外（trap_loc を壊さない）。
    assert _detect("来週は東京から大阪へ出張します。") == []
    assert _detect("北海道の気候について調べています。") == []


def test_compound_words_not_detected_as_address() -> None:
    # 都道府県直後にマーカーが来る複合語（都市部・市場・都民 等）は住所でない。
    for t in ["東京都市部の再開発", "京都府市場調査の結果", "東京都心部の混雑",
              "大阪府民の声を聞く", "東京都議会の議決"]:
        assert _detect(t) == [], t
    # 1文字市名の実在住所は拾う（堺市・津市）。
    assert (EntityType.ADDRESS, "大阪府堺市堺区") in _detect("大阪府堺市堺区で開催")


def test_postal_requires_marker() -> None:
    # 〒 の無い裸の 3-4 桁は住所として拾わない（誤検出抑制）。
    assert _detect("整理番号は150-0001です。") == []


# ---- パイプライン統合 ----

def test_address_layer_opt_in_recall(corpus: list[Case], clients_csv: str) -> None:
    sub = [c for c in corpus if c.category == "address"]
    assert sub
    off = evaluate(sub, [make_pipeline(Config(), clients_csv)])
    on = evaluate(sub, [make_pipeline(Config(), clients_csv, use_address=True)])
    assert off.type_recall(EntityType.ADDRESS) < 1.0      # 既定では拾わない
    assert on.type_recall(EntityType.ADDRESS) == 1.0, on.summary()


def test_address_roundtrip(corpus: list[Case], clients_csv: str) -> None:
    on = make_pipeline(Config(), clients_csv, use_address=True)
    for case in [c for c in corpus if c.category == "address"]:
        spans = on.detect(case.text)
        m = mask(case.text, spans)
        assert unmask(m.masked_text, m.mapping).text == case.text


def test_address_layer_no_false_positive_on_traps(corpus: list[Case], clients_csv: str) -> None:
    # 住所層を有効にしても単独地名トラップで誤検出しない。
    on = make_pipeline(Config(), clients_csv, use_address=True)
    for case in [c for c in corpus if c.category == "trap-loc"]:
        spans = [s for s in on.detect(case.text) if s.type == EntityType.ADDRESS]
        assert spans == []


# ---- ハイフン類バリアント（2026-07 P7後レビュー修正 2）----

def test_postal_code_hyphen_variants() -> None:
    # NFKC で '-' に吸収されないハイフン類（− ‐ ー 等）でも郵便番号を拾う。
    det = AddressDetector()
    for h in ("-", "−", "‐", "ー", "－"):
        spans = det.detect_shadow(f"〒150{h}0001 に送付")
        assert spans and spans[0].type == EntityType.ADDRESS, f"hyphen {h!r} missed"


def test_address_body_hyphen_variants() -> None:
    # 番地区切りのハイフン類バリアントで住所本体が途切れない。
    det = AddressDetector()
    text = "大阪府大阪市北区梅田3−1−1にあります"  # U+2212
    spans = det.detect_shadow(text)
    assert spans, "address with U+2212 separators missed"
    s = spans[0]
    assert text[s.start:s.end] == "大阪府大阪市北区梅田3−1−1"
