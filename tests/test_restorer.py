"""復元エンジンの回帰テスト（Planv2 §6.2）。

全角数字に改変されたプレースホルダの「静かな失敗」回帰:
_lenient_pattern が ASCII 番号でしか照合せず、一方で未解決スキャン(_LENIENT_ANY)は
全角数字を \\d で拾って int() 正規化するため、「復元されないのに unresolved にも
載らない」非対称が生じていた。番号を半角/全角どちらでも照合するよう修正済み。
"""

from __future__ import annotations

from namemask.core.restorer import unmask

_FW = {ord(str(d)): chr(0xFF10 + d) for d in range(10)}


def test_fullwidth_digit_placeholder_is_restored() -> None:
    mapping = {"[[組織_1]]": "株式会社アオヤマ商事", "[[人名_1]]": "高橋"}
    resp = "【組織_1】の[人名_1]について、[[組織１]]の方針は…"
    r = unmask(resp, mapping)
    assert "[[組織１]]" not in r.text
    assert r.text == "株式会社アオヤマ商事の高橋について、株式会社アオヤマ商事の方針は…"
    assert r.unresolved == []


def test_fullwidth_multidigit_index_restored() -> None:
    mapping = {"[[組織_12]]": "X社"}
    r = unmask("契約先は[[組織１２]]です。", mapping)
    assert r.text == "契約先はX社です。"
    assert r.unresolved == []


def test_genuinely_unknown_placeholder_flagged_even_fullwidth() -> None:
    # mapping に無い番号は、半角でも全角でも unresolved に載る（静かに消えない）。
    mapping = {"[[組織_1]]": "アオヤマ"}
    r = unmask("[[組織_1]] と [[人名_9]] と [[組織９]]", mapping)
    assert "[[組織_9]]" not in r.unresolved  # そのままの残骸を報告
    assert any("人名" in u for u in r.unresolved)
    assert any("組織" in u and ("9" in u or "９" in u) for u in r.unresolved)


def test_fullwidth_digit_roundtrip_via_token_mutation() -> None:
    # mask→（トークンの数字だけ全角化した応答）→unmask で原文復元。
    from namemask.core.replacer import mask
    from namemask.types import Span

    text = "アオヤマ商事と高橋について。"
    spans = [Span(0, 6, "ORGANIZATION"), Span(7, 9, "PERSON")]
    m = mask(text, spans)
    mutated = m.masked_text.translate(_FW)  # [[組織_1]] -> [[組織_１]]
    assert mutated != m.masked_text
    r = unmask(mutated, m.mapping)
    assert r.text == text
