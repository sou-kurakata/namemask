"""NER の fail-safe 検証（Planv2 §5 / §5.5）— **常に実行する**。

このファイルは importorskip を置かない。spacy/GiNZA が無い環境こそ fail-safe が
効くべき環境であり、そこで skip されては安全保証が無検証になる（P5 レビュー指摘）。
モデルがロードできない状況で NER が [] を返し、決定的層によるマスクを壊さないことを、
spacy の有無に関わらず確認する。
"""

from __future__ import annotations

from namemask.detectors.ner import NerDetector


def test_ner_failsafe_on_unloadable_model() -> None:
    # spacy 未導入なら import 失敗、導入済みでも存在しないモデル名でロード失敗。
    # いずれの経路でも例外を投げず [] を返す。
    det = NerDetector(model="__no_such_model__")
    assert det.detect("佐々木一郎が担当です。") == []
    assert det.detect("") == []
    # 2回目以降もロード再試行せず安定して [] を返す（_load_failed 記憶）。
    assert det.detect("株式会社アオヤマ商事") == []


def test_ner_failsafe_pipeline_still_masks_deterministically(clients_csv: str) -> None:
    """NER がロード不能でも、決定的層によるマスクは残る（use_ner=True でも安全）。"""
    from namemask.config import Config
    from namemask.pipeline.build import make_pipeline
    from namemask.types import EntityType

    pipe = make_pipeline(Config(), clients_csv, use_ner=True)
    # NER 層のモデル名を存在しないものへ差し替え、fail-safe 経路を強制する。
    for det in pipe._detectors:
        if getattr(det, "name", None) == "ner":
            det._model = "__no_such_model__"
    spans = pipe.detect("株式会社アオヤマ商事の山田様より連絡がありました。")
    got = {s.type for s in spans}
    # 決定的層で ORGANIZATION と PERSON は拾える（NER 不在でもマスクは残る）。
    assert EntityType.ORGANIZATION in got
    assert EntityType.PERSON in got
