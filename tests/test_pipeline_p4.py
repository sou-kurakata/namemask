"""P4 受け入れ（Planv2 §10 / §11 P4）— NER で全体 recall の目標到達を確認。

NER 追加で「敬称の無い署名内人名」等の未知固有名詞を拾い、全体 recall ≥ 0.95
（§10）に到達すること、precision 下限（≥0.70）と round-trip を維持することを確認。
GiNZA 未導入なら module skip。
"""

from __future__ import annotations

import pytest

pytest.importorskip("spacy", reason="spacy/ja_ginza 未導入")

from eval import Case, evaluate  # noqa: E402
from namemask.config import Config  # noqa: E402
from namemask.core import mask, unmask  # noqa: E402
from namemask.detectors.ner import NerDetector  # noqa: E402
from namemask.pipeline.build import make_pipeline  # noqa: E402


def _skip_if_no_model() -> None:
    det = NerDetector()
    det._ensure_loaded()
    if det._nlp is None:
        pytest.skip("ja_ginza モデルをロードできない")


@pytest.fixture(scope="module")
def pipelines(clients_csv: str):
    _skip_if_no_model()
    off = make_pipeline(Config(), clients_csv, use_ner=False)
    on = make_pipeline(Config(), clients_csv, use_ner=True)
    return off, on


@pytest.fixture(scope="module")
def reports(corpus: list[Case], pipelines):
    off, on = pipelines
    return evaluate(corpus, [off]), evaluate(corpus, [on])


def test_ner_improves_recall(reports) -> None:
    off_rep, on_rep = reports
    assert on_rep.recall > off_rep.recall, (
        f"NER off={off_rep.recall:.4f} on={on_rep.recall:.4f}"
    )


def test_overall_recall_meets_target(reports) -> None:
    # §10: 全体 recall（partial 基準）≥ 0.95
    _, on_rep = reports
    assert on_rep.recall >= 0.95, on_rep.summary()


def test_person_recall_improves(reports) -> None:
    from namemask.types import EntityType
    off_rep, on_rep = reports
    assert on_rep.type_recall(EntityType.PERSON) > off_rep.type_recall(EntityType.PERSON)


def test_precision_floor_with_ner(reports) -> None:
    # §10: precision ≥ 0.70（NER の過剰検出を許容する下限）
    _, on_rep = reports
    assert on_rep.precision >= 0.70, on_rep.summary()


def test_roundtrip_with_ner(corpus: list[Case], pipelines) -> None:
    _, on = pipelines
    for case in corpus:
        spans = on.detect(case.text)
        m = mask(case.text, spans)
        r = unmask(m.masked_text, m.mapping)
        assert r.text == case.text, f"[{case.id}] round-trip failed"
