"""NER ラベルマッピングの検証（Planv2 §5.5）— GiNZA 非依存。"""

from __future__ import annotations

from namemask.detectors.ner_labels import map_label
from namemask.types import EntityType


def test_person_and_org_and_location_mapping() -> None:
    assert map_label("Person") == EntityType.PERSON
    assert map_label("Company") == EntityType.ORGANIZATION
    assert map_label("Corporation_Other") == EntityType.ORGANIZATION
    assert map_label("Organization_Other") == EntityType.ORGANIZATION
    assert map_label("City") == EntityType.LOCATION
    assert map_label("Province") == EntityType.LOCATION


def test_unknown_labels_return_none() -> None:
    # 数値・製品・役職などは未マッピング（呼び出し側で warning・破棄）。
    for lab in [
        "Age",
        "Date",
        "Phone_Number",
        "Email",
        "Title_Other",
        "Position_Vocation",
        "ID_Number",
        "NoSuchLabel",
    ]:
        assert map_label(lab) is None, lab
