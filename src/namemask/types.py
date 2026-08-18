"""コア型定義。

パイプライン全体で共有する不変のデータ構造をここに集約する。
座標はすべて「原文（正規化前）」基準。
"""

from __future__ import annotations

from dataclasses import dataclass, field


# エンティティ型。config やプレースホルダ生成の唯一の真実。
class EntityType:
    PERSON = "PERSON"
    ORGANIZATION = "ORGANIZATION"
    LOCATION = "LOCATION"
    ADDRESS = "ADDRESS"
    EMAIL = "EMAIL"
    PHONE = "PHONE"
    MYNUMBER = "MYNUMBER"


ALL_TYPES = (
    EntityType.PERSON,
    EntityType.ORGANIZATION,
    EntityType.LOCATION,
    EntityType.ADDRESS,
    EntityType.EMAIL,
    EntityType.PHONE,
    EntityType.MYNUMBER,
)

# プレースホルダ表示用の日本語ラベル（[[組織_1]] 等）。
# 外部AIが構造を壊しにくい形にするための、型 -> 日本語ラベルの対応表。
TYPE_LABEL_JA: dict[str, str] = {
    EntityType.PERSON: "人名",
    EntityType.ORGANIZATION: "組織",
    EntityType.LOCATION: "地名",
    EntityType.ADDRESS: "住所",
    EntityType.EMAIL: "メール",
    EntityType.PHONE: "電話",
    EntityType.MYNUMBER: "マイナンバー",
}

# 型解決の優先度（辞書 > 構造ルール > 正規表現 > NER）。
# 値が大きいほど信頼できる。統合層で型が競合したときに使う。
SOURCE_PRIORITY: dict[str, int] = {
    "denylist": 40,
    "structural": 30,
    "address": 25,  # 住所は決定的パターン。regex 系と同格〜やや上
    "regex": 20,
    "ner": 10,
    "llm": 5,
}
# テスト用スタブ検出器（detectors/stub.py）は登録しない。stub は golden /
# round-trip / eval のいずれでも単独で走り、実検出器と型競合を起こす場面が
# ないため優先度を持たせる理由がなく、万一本番経路に混入した場合に他層へ
# 勝たせないため。未登録のソースは _span_priority が 0 として扱う（ADR-0002）。


@dataclass(frozen=True)
class Span:
    """原文座標上の検出スパン。

    start/end は原文（正規化前）の文字インデックス（end 排他）。
    sources はどの検出層が拾ったか（レビュー画面の「検出根拠」表示用）。
    """

    start: int
    end: int
    type: str
    score: float = 1.0
    sources: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.start < 0 or self.end < 0:
            raise ValueError(f"span offsets must be non-negative: {self}")
        if self.end <= self.start:
            raise ValueError(f"span end must be > start: {self}")
        if self.type not in ALL_TYPES:
            raise ValueError(f"unknown entity type: {self.type!r}")

    def surface(self, text: str) -> str:
        return text[self.start : self.end]

    def overlaps(self, other: Span) -> bool:
        return self.start < other.end and other.start < self.end


@dataclass(frozen=True)
class Entity:
    """golden corpus の正解エンティティ（座標を持たない表層表現）。

    JSON 形式に対応。位置は本文から解決する。
    nth を指定すると、その表記の n 番目（0 始まり）の出現だけを正解とする
    （複合語トラップで「この出現だけが人名」を表現するため）。None なら全出現。
    """

    surface: str
    type: str
    nth: int | None = None

    def __post_init__(self) -> None:
        if self.type not in ALL_TYPES:
            raise ValueError(f"unknown entity type: {self.type!r}")


@dataclass(frozen=True)
class ReportItem:
    """レビュー用の1マスク項目。"""

    original: str
    token: str
    type: str
    sources: tuple[str, ...] = field(default_factory=tuple)


@dataclass
class MaskResult:
    """置換エンジンの出力。"""

    masked_text: str
    mapping: dict[str, str]  # token -> original surface
    report: list[ReportItem]


@dataclass
class RestoreResult:
    """復元エンジンの出力。"""

    text: str
    warnings: list[str] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)
