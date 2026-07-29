"""正規表現層 — EMAIL / PHONE / MYNUMBER。

影テキスト（NFKC 正規化済み）上で動く ShadowDetector。全角英数・全角記号は
半角へ吸収済みなので基本は半角前提で書く。ただし NFKC で吸収されない
ハイフン類（ー ‐ ― −）は電話番号用の文字クラスで明示的に許容する。
メールアドレスなど改善の予知あり。
"""

from __future__ import annotations

import re

from namemask.config import Config
from namemask.types import EntityType, Span

# NFKC で吸収されないハイフン類も含めた電話用ハイフン文字クラス。
_HYPHEN = r"[-ー−‐―ｰ]"

# EMAIL: 前後がメール識別子文字でないことを要求して部分切り出しを防ぐ。
# 境界は ASCII 限定にする。\w は日本語（は 等）にもマッチし、日本語直後の
# メールを誤って弾くため使わない。
_EMAIL = re.compile(
    r"(?<![A-Za-z0-9._%+\-])"
    r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}"
    r"(?![A-Za-z0-9\-])"
)

# PHONE: 数字列の前後に数字が無いこと（(?<!\d)…(?!\d)）で桁の途中切り出しを防ぐ。
# 日本の 0 始まりに限定。3分割ハイフン形は市外局番の桁数で分ける:
#   - 2桁市外局番は日本では 03/06 のみ。しかも 03/06 番号は 03-XXXX-XXXX の 4-4 固定。
#     任意の 0X-\d{1,4}-\d{3,4} を許すと日付 07-07-2026 等を誤検出するため 4-4 に限定。
#   - 携帯/フリーダイヤル/IP/地方局番は 3〜5桁（0\d{2,4}）で中間・末尾は可変。
#     5桁局番は実在する（04992=小笠原, 05769=白川村 等）。下限3桁が MM-DD 日付形式を
#     排除し続けるため、5桁許容でも 07-07-2026 / 2026-07-07 は誤検出しない。
# 加えてハイフン無し 10〜11桁も許容。
_PHONE_PATTERNS = [
    re.compile(r"(?<!\d)0[36]" + _HYPHEN + r"\d{4}" + _HYPHEN + r"\d{4}(?!\d)"),
    re.compile(r"(?<!\d)0\d{2,4}" + _HYPHEN + r"\d{1,4}" + _HYPHEN + r"\d{3,4}(?!\d)"),
    re.compile(r"(?<!\d)0\d{9,10}(?!\d)"),
]

# MYNUMBER: 12桁。前後に数字が無いこと。チェックディジット検証で真偽を確定。
_MYNUMBER = re.compile(r"(?<!\d)\d{12}(?!\d)")


def mynumber_check_digit(body11: str) -> int:
    """マイナンバー先頭11桁からチェックディジット（12桁目）を算出する。"""
    q = [2, 3, 4, 5, 6, 7, 2, 3, 4, 5, 6]
    p = [int(c) for c in body11][::-1]
    r = sum(p[n] * q[n] for n in range(11)) % 11
    return 0 if r <= 1 else 11 - r


def is_valid_mynumber(digits12: str) -> bool:
    if len(digits12) != 12 or not digits12.isdigit():
        return False
    return mynumber_check_digit(digits12[:11]) == int(digits12[11])


class RegexDetector:
    """EMAIL / PHONE / MYNUMBER の決定的検出（高信頼）。"""

    name = "regex"

    def __init__(self, config: Config | None = None) -> None:
        self._extra: list[tuple[re.Pattern[str], str]] = []
        if config is not None:
            for item in config.regex_extra_patterns:
                pat = item.get("pattern")
                typ = item.get("type")
                if pat and typ in vars(EntityType).values():
                    self._extra.append((re.compile(pat), typ))

    def detect_shadow(self, shadow: str) -> list[Span]:
        spans: list[Span] = []

        for m in _EMAIL.finditer(shadow):
            spans.append(self._span(m.start(), m.end(), EntityType.EMAIL))

        for pat in _PHONE_PATTERNS:
            for m in pat.finditer(shadow):
                spans.append(self._span(m.start(), m.end(), EntityType.PHONE))

        for m in _MYNUMBER.finditer(shadow):
            if is_valid_mynumber(m.group()):
                spans.append(self._span(m.start(), m.end(), EntityType.MYNUMBER))

        for pat, typ in self._extra:
            for m in pat.finditer(shadow):
                if m.end() > m.start():
                    spans.append(self._span(m.start(), m.end(), typ))

        return spans

    def _span(self, start: int, end: int, type_: str) -> Span:
        return Span(start=start, end=end, type=type_, score=1.0, sources=(self.name,))
