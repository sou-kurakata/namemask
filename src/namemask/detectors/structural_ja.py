"""構造ルール層 — recall の主力。

日本語の強い表層手がかり（法人格・敬称）を NER に頼らず決定的に拾う。
影テキスト上で動く ShadowDetector。
"""

from __future__ import annotations

import re

from namemask.config import Config
from namemask.lexicon import (
    DEFAULT_PERSON_STOPWORDS,
    DEPT_ROLE_BOUNDARY,
    GENERAL_WORD_STOPWORDS,
    HONORIFICS_ORG,
    HONORIFICS_PERSON,
    LEGAL_FORMS,
    ORG_NAME_CLASS,
    PERSON_NAME_CLASS,
)
from namemask.types import EntityType, Span


def _legal_alt() -> str:
    # 長い法人格を先に（部分マッチ回避）。括弧をエスケープ。
    forms = sorted(LEGAL_FORMS, key=len, reverse=True)
    return "|".join(re.escape(f) for f in forms)


class StructuralDetector:
    name = "structural"

    def __init__(self, config: Config | None = None) -> None:
        cfg = config or Config()
        self._person_max = cfg.person_max_len
        self._org_max = cfg.org_name_max_len
        # config 由来のストップワードに、常に除外する一般語を加える。
        self._stopwords = set(cfg.person_stopwords or DEFAULT_PERSON_STOPWORDS) | set(
            GENERAL_WORD_STOPWORDS
        )
        self._dept_boundary = set(DEPT_ROLE_BOUNDARY)

        legal = _legal_alt()
        org = ORG_NAME_CLASS
        # 前置型: 法人格 + 名称（右方向に最長の名称ラン）。
        self._org_prefix = re.compile(f"(?:{legal})([{org}]{{1,{self._org_max}}})")
        # 後置型: 名称ラン + 法人格。名称の先頭は名称文字以外に接する（ラン境界）。
        self._org_suffix = re.compile(f"(?<![{org}])([{org}]{{1,{self._org_max}}})(?:{legal})")
        # 御中 の直前は組織候補。
        org_h = "|".join(re.escape(h) for h in HONORIFICS_ORG)
        self._org_keigo = re.compile(f"(?<![{org}])([{org}]{{1,{self._org_max}}})(?:{org_h})")
        # 敬称アンカー人名: 直前 1〜max 文字（漢字/カタカナ/英字）。
        person_h = "|".join(re.escape(h) for h in HONORIFICS_PERSON)
        self._person = re.compile(f"([{PERSON_NAME_CLASS}]{{1,{self._person_max}}})(?:{person_h})")

    def detect_shadow(self, shadow: str) -> list[Span]:
        spans: list[Span] = []

        # ORG（前置・後置）: 法人格を含む一致は誤検出がほぼ無く高信頼。
        # スパンは法人格を含む全体（株式会社アオヤマ商事）。
        for pat in (self._org_prefix, self._org_suffix):
            for m in pat.finditer(shadow):
                spans.append(
                    Span(
                        m.start(), m.end(), EntityType.ORGANIZATION, score=1.0, sources=(self.name,)
                    )
                )

        # ORG（御中）: 御中 は敬称なので名称部（group 1）のみをスパン化。
        for m in self._org_keigo.finditer(shadow):
            spans.append(
                Span(m.start(1), m.end(1), EntityType.ORGANIZATION, score=0.9, sources=(self.name,))
            )

        # PERSON: 名前部分のみをスパン化（敬称は境界判定にのみ使用）。
        for m in self._person.finditer(shadow):
            name = m.group(1)
            start = m.start(1)
            # 左境界ガード: 部署・役職境界が食い込んでいたら直後で切る
            # （営業部田中様 → 田中）。最後の境界文字の右側を採用。
            for i in range(len(name) - 1, -1, -1):
                if name[i] in self._dept_boundary:
                    start = m.start(1) + i + 1
                    name = name[i + 1 :]
                    break
            if not name or name in self._stopwords:
                continue
            spans.append(Span(start, m.end(1), EntityType.PERSON, score=0.9, sources=(self.name,)))

        return spans
