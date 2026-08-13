"""P3 受け入れ（Planv2 §10 / §11 P3）— 実パイプラインでの決定的検出。

P3 の到達目標: 辞書100% / 正規表現100% / 法人格98%（NER なしで recall の床）。
全体 recall 95%（§10）は敬称の無い署名内人名を NER が拾う P4 以降で達成する。
"""

from __future__ import annotations

import pytest

from eval import Case, evaluate
from namemask.core import mask, unmask
from namemask.types import EntityType

REGEX_TYPES = (EntityType.EMAIL, EntityType.PHONE, EntityType.MYNUMBER)
LEGAL_CATEGORIES = {"org-prefix", "org-suffix", "org-abbr", "org-glyph", "org-fullwidth"}
DICT_CATEGORIES = {"org-core", "dict-variant"}
TRAP_CATEGORIES = {
    "trap-person",
    "trap-org",
    "trap-loc",
    "mynumber-invalid",
    "trap-role",
    "trap-phone",
}


@pytest.fixture(scope="module")
def report(corpus: list[Case], pipeline):
    return evaluate(corpus, [pipeline])


def test_regex_types_recall_100(report) -> None:
    for t in REGEX_TYPES:
        assert report.type_recall(t) == 1.0, (
            f"{t} recall={report.type_recall(t)}\n{report.summary()}"
        )


def test_dictionary_clients_recall_100(corpus: list[Case], pipeline) -> None:
    subset = [c for c in corpus if c.category in DICT_CATEGORIES]
    rep = evaluate(subset, [pipeline])
    assert rep.type_recall(EntityType.ORGANIZATION) == 1.0, rep.summary()


def test_legal_form_org_recall_98(corpus: list[Case], pipeline) -> None:
    subset = [c for c in corpus if c.category in LEGAL_CATEGORIES]
    rep = evaluate(subset, [pipeline])
    assert rep.type_recall(EntityType.ORGANIZATION) >= 0.98, rep.summary()


def test_precision_floor(report) -> None:
    assert report.precision >= 0.70, report.summary()


def test_no_false_positives(report) -> None:
    """P3.5: 複合語伝播・一般語・部署食い込みの誤検出がゼロ（precision 1.0）。"""
    assert report.false_positives == [], report.summary()


def test_dict_variant_recall_100(corpus: list[Case], pipeline) -> None:
    """P3.5-1: 辞書のハイフン/空白バリアントも fold 影で 100% 拾う。"""
    subset = [c for c in corpus if c.category == "dict-variant"]
    assert subset
    rep = evaluate(subset, [pipeline])
    assert rep.type_recall(EntityType.ORGANIZATION) == 1.0, rep.summary()


def test_person_dept_boundary(corpus: list[Case], pipeline) -> None:
    """P3.5-2: 部署名＋人名＋敬称で、人名だけを正確に（exact で）拾う。"""
    subset = [c for c in corpus if c.category == "person-dept"]
    assert subset
    rep = evaluate(subset, [pipeline])
    assert rep.exact_recall == 1.0, rep.summary()


def test_compound_trap_no_overmask(corpus: list[Case], pipeline) -> None:
    """P3.5-3: 複合語内部の同一表記へ伝播しない（青葉区役所/大和魂）。"""
    for case in corpus:
        if case.category != "compound-trap":
            continue
        ent = case.entities[0]
        first = case.text.find(ent.surface)
        second = case.text.find(ent.surface, first + len(ent.surface))
        assert second != -1, f"[{case.id}] test setup: needs 2 occurrences"
        spans = pipeline.detect(case.text)
        # 2つ目の出現位置はどのスパンにも覆われない
        assert all(not (s.start <= second < s.end) for s in spans), (
            f"[{case.id}] propagated into compound word at {second}"
        )


def test_layer_contribution_ablation(corpus: list[Case], clients_csv: str) -> None:
    """P3.5-4: 層別寄与を真のアブレーション（層を抜いて再評価）で測る。"""
    from eval import evaluate_layer_contribution
    from namemask.config import Config
    from namemask.pipeline.build import ALL_LAYER_NAMES, make_pipeline

    _full, contrib = evaluate_layer_contribution(
        corpus,
        lambda d: make_pipeline(Config(), clients_csv, d),
        ALL_LAYER_NAMES,
    )
    # 各決定的層は recall に正の寄与を持つ（source フィルタ方式では出せない値）。
    assert contrib["regex"] > 0, contrib
    assert contrib["structural"] > 0, contrib
    assert contrib["denylist"] > 0, contrib


def test_pipeline_roundtrip_all_cases(corpus: list[Case], pipeline) -> None:
    """実パイプラインの検出スパンで mask->unmask しても原文完全復元（不変条件§2-1）。

    統合層の出力が非重複であることも（重なりなら mask が例外）ここで担保。
    """
    for case in corpus:
        spans = pipeline.detect(case.text)
        m = mask(case.text, spans)
        r = unmask(m.masked_text, m.mapping)
        assert r.text == case.text, f"[{case.id}] round-trip failed"


def test_traps_produce_no_detection(corpus: list[Case], pipeline) -> None:
    """誤検出トラップ（皆さん/お客様/制度説明/単独地名/CD不正）で検出ゼロ。"""
    for case in corpus:
        if case.category in TRAP_CATEGORIES:
            spans = pipeline.detect(case.text)
            assert spans == [], (
                f"[{case.id}] unexpected detections: {[case.text[s.start : s.end] for s in spans]}"
            )
