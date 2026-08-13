"""正規表現層のテスト（Planv2 §5.2 / §10）。"""

from __future__ import annotations

from namemask.detectors.normalizing import NormalizingDetector
from namemask.detectors.regex_ja import (
    RegexDetector,
    is_valid_mynumber,
    mynumber_check_digit,
)
from namemask.types import EntityType


def _shadow_types(text: str) -> list[tuple[str, str]]:
    det = RegexDetector()
    return [(s.type, text[s.start : s.end]) for s in det.detect_shadow(text)]


def test_mynumber_check_digit_known_values() -> None:
    assert mynumber_check_digit("12345678901") == 8
    assert is_valid_mynumber("123456789018")
    assert not is_valid_mynumber("123456789019")  # CD 不正
    assert not is_valid_mynumber("12345678901")  # 桁不足


def test_mynumber_valid_detected_invalid_ignored() -> None:
    assert (EntityType.MYNUMBER, "123456789018") in _shadow_types("番号123456789018です")
    # チェックディジット不正は検出しない
    assert _shadow_types("番号123456789019です") == []
    # 12桁でも別番号（CD不正）は拾わない
    assert (EntityType.MYNUMBER, "123456789012") not in _shadow_types("注文123456789012")


def test_email_variants() -> None:
    assert (EntityType.EMAIL, "contact@example.org") in _shadow_types(
        "詳細は contact@example.org まで"
    )
    assert (EntityType.EMAIL, "billing.dept+inv@sub.example.co.jp") in _shadow_types(
        "宛先 billing.dept+inv@sub.example.co.jp"
    )


def test_email_directly_after_japanese() -> None:
    """日本語直後のメールも拾う（\\w 境界バグの回帰）。"""
    det = NormalizingDetector(RegexDetector())
    text = "送付先はｉｎｆｏ＠ｅｘａｍｐｌｅ．ｃｏｍです。"  # 全角・は直後
    spans = det.detect(text)
    assert len(spans) == 1
    assert spans[0].type == EntityType.EMAIL
    assert text[spans[0].start : spans[0].end] == "ｉｎｆｏ＠ｅｘａｍｐｌｅ．ｃｏｍ"


def test_phone_variants() -> None:
    for t, expect in [
        ("固定 06-6400-1234 です", "06-6400-1234"),
        ("携帯 090-8765-4321", "090-8765-4321"),
        ("フリー 0120-123-456 受付", "0120-123-456"),
        ("IP 050-1111-2222 まで", "050-1111-2222"),
        ("FAX 0664001234 へ", "0664001234"),
        ("小笠原 04992-2-1234 まで", "04992-2-1234"),  # 5桁市外局番
        ("白川村 05769-6-1234 です", "05769-6-1234"),  # 5桁市外局番
    ]:
        assert (EntityType.PHONE, expect) in _shadow_types(t), t


def test_phone_does_not_match_dates() -> None:
    # 日付は電話番号として誤検出しない（2桁市外局番は 03/06 の 4-4 のみ）。
    for t in [
        "締切は07-07-2026です",
        "03-07-2026",
        "06-30-2025",
        "01-02-2020",
        "12-31-2025",
        "03-1-2026",
    ]:
        assert not [x for x in _shadow_types(t) if x[0] == EntityType.PHONE], t


def test_phone_fullwidth_and_hyphen_variants() -> None:
    det = NormalizingDetector(RegexDetector())
    for text, surface in [
        ("お問い合わせは０３－１２３４－５６７８まで", "０３－１２３４－５６７８"),
        ("携帯は090ー1111ー2222です", "090ー1111ー2222"),
        ("代表 03‐9999‐0000 へ", "03‐9999‐0000"),
    ]:
        spans = det.detect(text)
        got = [text[s.start : s.end] for s in spans if s.type == EntityType.PHONE]
        assert surface in got, (text, got)
