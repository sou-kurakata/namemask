"""住所検出層 — 日本の住所・郵便番号。


影テキスト上で動く ShadowDetector。**単独の地名は対象にしない**（初版方針・
trap_loc を壊さない）。郵便番号（〒付き）と、都道府県から始まり市区町村/番地を
含む「住所」だけを決定的に拾う。

判定: 都道府県 + 住所本体（漢字・カタカナ・数字・ハイフン）で、かつ
  (a) 本体に数字（番地）を含む、または
  (b) 市区町村郡マーカーが本体の先頭以外に現れる
もの。「北海道の気候」等の単独県名は本体が空/助詞で停止するため対象外。
(b) の「先頭以外」条件は、実在住所では都道府県と最初の市/区/郡の間に必ず市名・区名
が入る（東京都[渋谷]区、大阪府[大阪]市）ことを利用し、都市部・市場調査・都民 等の
複合語（都道府県直後にマーカーが来る）を住所と誤判定しないためのガード。
"""

from __future__ import annotations

import re

from namemask.normalize import HYPHEN_CHARS
from namemask.types import EntityType, Span

# NFKC で吸収されないハイフン類（− ‐ ― ー 等）も許容する（normalize.py と共有）。
_HYPHEN = "".join(re.escape(c) for c in HYPHEN_CHARS)

_PREFECTURES = (
    "北海道|青森県|岩手県|宮城県|秋田県|山形県|福島県|茨城県|栃木県|群馬県|"
    "埼玉県|千葉県|東京都|神奈川県|新潟県|富山県|石川県|福井県|山梨県|長野県|"
    "岐阜県|静岡県|愛知県|三重県|滋賀県|京都府|大阪府|兵庫県|奈良県|和歌山県|"
    "鳥取県|島根県|岡山県|広島県|山口県|徳島県|香川県|愛媛県|高知県|福岡県|"
    "佐賀県|長崎県|熊本県|大分県|宮崎県|鹿児島県|沖縄県"
)
# 住所本体（ひらがな除外で助詞・文の続きで停止）。丁目番地号は漢字なので一-龥に含む。
# 番地区切りのハイフンは NFKC 非吸収のバリアント（− ‐ ー 等）を全て許容する。
_BODY = f"[一-龥ァ-ヶ0-9{_HYPHEN}]"
_ADDRESS_RE = re.compile(f"(?P<pref>{_PREFECTURES})(?P<body>(?:{_BODY}){{1,40}})")
# 郵便番号は 〒 付きのみ（裸の 3-4 桁誤検出を避ける）。区切りもハイフン類を許容。
_POSTAL_RE = re.compile(rf"〒\s?\d{{3}}[{_HYPHEN}]\d{{4}}")

_ADDRESS_MARKERS = "市区町村郡"


class AddressDetector:
    name = "address"

    def detect_shadow(self, shadow: str) -> list[Span]:
        spans: list[Span] = []
        for m in _POSTAL_RE.finditer(shadow):
            spans.append(self._span(m.start(), m.end()))
        for m in _ADDRESS_RE.finditer(shadow):
            body = m.group("body")
            has_digit = any(c.isdigit() for c in body)
            # マーカーは本体の先頭以外（＝市名・区名の後）に現れる場合のみ有効。
            # 都道府県直後にマーカーが来る複合語（都市部・市場調査 等）を除外する。
            marker_after_name = any(k in body[1:] for k in _ADDRESS_MARKERS)
            if has_digit or marker_after_name:
                spans.append(self._span(m.start(), m.end()))
        return spans

    def _span(self, start: int, end: int) -> Span:
        return Span(start, end, EntityType.ADDRESS, score=1.0, sources=(self.name,))
