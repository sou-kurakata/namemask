"""辞書層 — 既知の取引先を100%落とす。

clients.csv からバリアントを自動展開し、pyahocorasick で影テキストを一括走査。
影テキスト（NFKC 正規化済み）上で照合するため、キーも同じ正規化を施して対称に
する。日本語は分かち書きが無いため部分文字列マッチ必須（ADR-006）。
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

import ahocorasick

from namemask.config import Config
from namemask.lexicon import strip_legal_form
from namemask.normalize import fold_for_dict
from namemask.types import ALL_TYPES, EntityType, Span

# コア名に法人格を付け直す際の代表表記（前置・後置の両方を生成）。
_CANONICAL_LEGAL = ("株式会社", "有限会社", "(株)", "(有)")


@dataclass
class ClientRow:
    name: str
    type: str = EntityType.ORGANIZATION
    aliases: list[str] = field(default_factory=list)


def load_clients_csv(path: Path | str) -> list[ClientRow]:
    rows: list[ClientRow] = []
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            name = (r.get("name") or "").strip()
            if not name:
                continue
            typ = (r.get("type") or EntityType.ORGANIZATION).strip()
            if typ not in ALL_TYPES:
                typ = EntityType.ORGANIZATION
            aliases_raw = (r.get("aliases") or "").strip()
            aliases = [a.strip() for a in aliases_raw.split("|") if a.strip()]
            rows.append(ClientRow(name=name, type=typ, aliases=aliases))
    return rows


def expand_variants(row: ClientRow, min_core_len: int) -> set[str]:
    """1取引先の照合バリアント集合を生成する。"""
    variants: set[str] = set()
    name = row.name
    variants.add(name)

    lf, core = strip_legal_form(name)
    if lf and core:
        # 法人格付き別表記（前置・後置＋代表法人格）。
        for legal in _CANONICAL_LEGAL:
            variants.add(legal + core)   # 前置
            variants.add(core + legal)   # 後置
        # コア名単体は2文字以下だと誤マッチ多発のため登録しない。
        if len(core) >= min_core_len:
            variants.add(core)

    variants.update(row.aliases)

    # 空キーを除外し、fold（NFKC＋空白除去＋ハイフン同一視）でキーを正規化して
    # fold 影テキストと対称にする（ADR-007）。fold 後に空になるキーも除外。
    folded = {fold_for_dict(v) for v in variants if v}
    return {v for v in folded if v}


class DenylistDetector:
    """辞書掲載の取引先を全バリアント表記で拾う。"""

    name = "denylist"

    def __init__(self, rows: list[ClientRow], min_core_len: int = 3) -> None:
        self._automaton = ahocorasick.Automaton()
        self._key_type: dict[str, str] = {}
        for row in rows:
            for key in expand_variants(row, min_core_len):
                # 同一キーが型衝突する場合は先勝ち（通常は全て ORGANIZATION）。
                if key not in self._key_type:
                    self._key_type[key] = row.type
                    self._automaton.add_word(key, (key, row.type))
        if self._key_type:
            self._automaton.make_automaton()

    @classmethod
    def from_config(cls, config: Config) -> DenylistDetector:
        rows: list[ClientRow] = []
        if config.clients_csv and Path(config.clients_csv).exists():
            rows += load_clients_csv(config.clients_csv)
        if config.persons_csv and Path(config.persons_csv).exists():
            prows = load_clients_csv(config.persons_csv)
            for p in prows:
                p.type = EntityType.PERSON
            rows += prows
        return cls(rows, min_core_len=config.denylist_min_core_len)

    def detect_shadow(self, shadow: str) -> list[Span]:
        if not self._key_type:
            return []
        spans: list[Span] = []
        for end_idx, (key, typ) in self._automaton.iter(shadow):
            start = end_idx - len(key) + 1
            spans.append(
                Span(start, end_idx + 1, typ, score=1.0, sources=(self.name,))
            )
        return spans
