""" スタブ検出器。

golden の正解エンティティ（surface, type）を受け取り、本文中の全出現を
スパン化して返す。これにより「可逆性（round-trip）」を検出精度から切り離し、
先に 100% を確定させる。実検出器は 本 Protocol を満たして差し替える。

同一表記は本文中の全位置を拾う。これにより
マスク後テキストに被マスク表記の残存が起きない。
"""

from __future__ import annotations

from namemask.types import Entity, Span


class GoldenStubDetector:
    name = "stub"

    def __init__(self, entities: list[Entity]) -> None:
        # 長い表層を先に消費し、短い表層が長い表層に食い込むのを防ぐ。
        self._entities = sorted(entities, key=lambda e: len(e.surface), reverse=True)

    def detect(self, text: str) -> list[Span]:
        consumed = [False] * len(text)
        spans: list[Span] = []
        for ent in self._entities:
            surface = ent.surface
            if not surface:
                continue
            # nth 指定時はその出現のみ、未指定なら全出現を対象にする。
            if ent.nth is not None:
                starts = self._nth_occurrence(text, surface, ent.nth)
            else:
                starts = self._all_occurrences(text, surface)
            for start in starts:
                end = start + len(surface)
                if not any(consumed[start:end]):
                    for i in range(start, end):
                        consumed[i] = True
                    spans.append(
                        Span(start=start, end=end, type=ent.type,
                             score=1.0, sources=(self.name,))
                    )
        spans.sort(key=lambda s: (s.start, s.end))
        return spans

    @staticmethod
    def _all_occurrences(text: str, surface: str) -> list[int]:
        out: list[int] = []
        i = text.find(surface)
        while i != -1:
            out.append(i)
            i = text.find(surface, i + 1)
        return out

    @classmethod
    def _nth_occurrence(cls, text: str, surface: str, nth: int) -> list[int]:
        occ = cls._all_occurrences(text, surface)
        return [occ[nth]] if 0 <= nth < len(occ) else []
