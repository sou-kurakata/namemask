"""NER 層
— GiNZA による未知固有名詞の拾い上げ。

決定的層（正規表現・構造ルール・辞書）で拾えない「手がかりの無い固有名詞」
（署名内の敬称なし人名など）を補う。GiNZA は原文をそのまま解析し原文座標の
スパンを返すため、影テキスト変換は不要（本検出器は Detector 直系）。

fail-safe : spacy/モデルが無い・ロード失敗・推論失敗の
いずれでも [] を返し、決定的マスクの床を壊さない。
"""

from __future__ import annotations

import logging

from namemask.config import Config
from namemask.detectors.ner_labels import map_label
from namemask.types import EntityType, Span

logger = logging.getLogger(__name__)

_DEFAULT_ENABLED = (EntityType.PERSON, EntityType.ORGANIZATION)


class NerDetector:
    """GiNZA NER 検出器（低スコア・追加専用の recall 補完）。

    enabled_types に無い型（既定では LOCATION）はマッピングしても emit しない。
    未知ラベルはラベル名のみを一度だけ warning に出す（本文は絶対に出さない）。
    """

    name = "ner"

    def __init__(
        self,
        model: str = "ja_ginza",
        enabled_types=_DEFAULT_ENABLED,
        score: float = 0.5,
        split_mode: str = "C",
    ) -> None:
        self._model = model
        self._enabled = set(enabled_types)
        self._score = score
        self._split_mode = split_mode
        self._nlp = None
        self._load_failed = False
        self._warned: set[str] = set()

    @classmethod
    def from_config(cls, config: Config) -> NerDetector:
        ner = config.section("ner")
        return cls(
            model=ner.get("engine", "ja_ginza"),
            score=float(ner.get("score_threshold", 0.5)),
        )

    def _ensure_loaded(self) -> None:
        if self._nlp is not None or self._load_failed:
            return
        try:
            import spacy
        except Exception as e:  # spacy 未導入 → NER 無効（決定的層は残る）
            self._load_failed = True
            logger.warning(
                "NER disabled: spacy import failed (%s). Deterministic layers remain.",
                type(e).__name__,
            )
            return
        # GiNZA 5.2 の compound_splitter 設定（split_mode=None）が新しい
        # confection で弾かれるため、split_mode を明示上書きしてロードする。
        override = {"components": {"compound_splitter": {"split_mode": self._split_mode}}}
        for kwargs in ({"config": override}, {}):
            try:
                self._nlp = spacy.load(self._model, **kwargs)
                return
            except Exception as e:
                last = e
        self._load_failed = True
        logger.warning(
            "NER disabled: could not load model %r (%s). Deterministic layers remain.",
            self._model,
            type(last).__name__,
        )

    def detect(self, text: str) -> list[Span]:
        if not text:
            return []
        self._ensure_loaded()
        if self._nlp is None:
            return []
        try:
            doc = self._nlp(text)
        except Exception as e:  # 推論失敗も fail-safe
            logger.warning("NER inference failed (%s); skipping.", type(e).__name__)
            return []

        spans: list[Span] = []
        for ent in doc.ents:
            typ = map_label(ent.label_)
            if typ is None:
                if ent.label_ not in self._warned:
                    self._warned.add(ent.label_)
                    logger.warning(
                        "NER: unmapped label %r (skipped; entity body not logged)",
                        ent.label_,
                    )
                continue
            if typ not in self._enabled:
                continue
            start, end = self._trim(text, ent.start_char, ent.end_char)
            if end > start:
                spans.append(Span(start, end, typ, score=self._score, sources=(self.name,)))
        return spans

    @staticmethod
    def _trim(text: str, start: int, end: int) -> tuple[int, int]:
        # 前後の空白・改行を除いて過剰マスクを抑える。
        while start < end and text[start].isspace():
            start += 1
        while end > start and text[end - 1].isspace():
            end -= 1
        return start, end
