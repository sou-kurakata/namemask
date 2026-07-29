"""GiNZA/spaCy（ENE 拡張固有表現）ラベル → 本ツール型 の対応表。

GiNZA v5（ja_ginza）は関根の拡張固有表現（ENE）体系のラベルを出す
（Person / Company / City / Corporation_Other …）。ここで PERSON /
ORGANIZATION / LOCATION に明示マッピングする。**マッピングに無いラベルは
黙って捨てず warning（ラベル名のみ・本文は出さない）** で扱う（呼び出し側）。

GiNZA-非依存の純データ＋純関数。単体テストで表の妥当性を検証できる。
"""

from __future__ import annotations

from namemask.types import EntityType

# 人名系
_PERSON_LABELS = {"Person"}

# 組織系（ENE の会社・法人・団体サブタイプを広く採る。recall 優先）。
_ORG_LABELS = {
    "Company",
    "Company_Group",
    "Corporation_Other",
    "Organization_Other",
    "International_Organization",
    "Government",
    "Cabinet",
    "Military",
    "Political_Organization_Other",
    "Political_Party",
    "Political_Organization",
    "Sports_Organization_Other",
    "Pro_Sports_Organization",
    "Sports_League",
    "Sports_Team",
    "Show_Organization",
    "Nonprofit_Organization",
    "Ethnic_Group_Other",
    "Nationality",
    "Family",
}

# 地名系（検出しても既定で emit しない。住所対応で有効化する）。
_LOCATION_LABELS = {
    "City",
    "County",
    "Province",
    "Country",
    "GPE_Other",
    "Region_Other",
    "Geological_Region_Other",
    "Continental_Region",
    "Domestic_Region",
    "Address",
    "Postal_Address",
    "Location_Other",
    "Mountain",
    "Island",
    "River",
    "Lake",
    "Sea",
    "Bay",
    "Canal",
    "Spa",
}

LABEL_MAP: dict[str, str] = {
    **{lab: EntityType.PERSON for lab in _PERSON_LABELS},
    **{lab: EntityType.ORGANIZATION for lab in _ORG_LABELS},
    **{lab: EntityType.LOCATION for lab in _LOCATION_LABELS},
}


def map_label(label: str) -> str | None:
    """ENE ラベルを本ツール型へ。未知ラベルは None（呼び出し側で warning）。"""
    return LABEL_MAP.get(label)
