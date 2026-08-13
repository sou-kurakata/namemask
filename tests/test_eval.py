"""評価ハーネス自体の正しさ検証（Planv2 §8.2）。

理想検出（stub=gold）だと全指標が 1.0 になり数式の検算にならない。
そこで「一部見逃し＋一部誤検出」の合成検出器を与え、手計算値と一致するか確認する。
これで recall/precision/exact/型別/層別寄与の計算経路を担保する。
"""

from __future__ import annotations

from eval import (
    Case,
    check_thresholds,
    evaluate,
    load_corpus,
    make_ideal_detector,
)
from namemask.types import Entity, EntityType, Span

P = EntityType.PERSON
L = EntityType.LOCATION


class _FakeDetector:
    """text="山田と田中" のみに反応。山田は正解、と はFP、田中は見逃す。"""

    name = "fake"

    def detect(self, text: str) -> list[Span]:
        if text == "山田と田中":
            return [
                Span(0, 2, P, sources=("fake",)),  # 山田: 正解（exact）
                Span(2, 3, L, sources=("fake",)),  # と: 誤検出
            ]
        return []


def _case() -> Case:
    return Case(
        id="t1",
        category="synthetic",
        text="山田と田中",
        entities=[Entity("山田", P), Entity("田中", P)],
    )


def test_eval_math_matches_hand_computation() -> None:
    rep = evaluate([_case()], [_FakeDetector()])

    # gold=2 (山田, 田中), pred=2 (山田, と)
    assert rep.gold_total == 2
    assert rep.pred_total == 2

    # recall: 山田 拾えた / 田中 見逃し -> 1/2
    assert rep.recall == 0.5
    # precision: 山田 正解 / と 誤検出 -> 1/2
    assert rep.precision == 0.5
    # exact: 山田 のみ完全一致 -> 1/2
    assert rep.exact_recall == 0.5
    # F1
    assert abs(rep.f1 - 0.5) < 1e-9

    # 型別 recall（PERSON のみ 2件中1件）
    assert rep.type_recall(P) == 0.5

    # 見逃し/誤検出の明細
    assert rep.false_negatives == [("t1", "田中", P)]
    assert rep.false_positives == [("t1", "と", L)]

    # 層別寄与: fake を外すと recall 0 -> 寄与 0.5
    assert abs(rep.layer_contribution["fake"] - 0.5) < 1e-9


def test_eval_empty_detectors_zero_recall() -> None:
    rep = evaluate([_case()], [])
    assert rep.recall == 0.0
    assert rep.pred_total == 0
    # 誤検出はゼロなので precision は定義上 1.0（分母0）
    assert rep.precision == 1.0


def test_threshold_gate_passes_for_real_pipeline(corpus, pipeline) -> None:
    """CI の eval ゲートと同じ判定をローカルでも回す（CLAUDE.md §6）。"""
    report = evaluate(corpus, [pipeline])
    checks = check_thresholds(corpus, report, pipeline)
    failed = [c.name for c in checks if not c.ok]
    assert not failed, f"閾値を下回っています: {failed}\n{report.summary()}"


def test_threshold_gate_actually_fails_when_recall_drops(corpus) -> None:
    """**ゲートが実際に噛むこと**を証明する。

    「常に緑のゲート」は無いのと同じ（CI では tee がこれを起こしていた）。
    辞書層を外したパイプラインなら、辞書ケースの recall が 1.0 を割るはず。
    """
    from namemask.config import Config
    from namemask.pipeline.build import make_pipeline

    degraded = make_pipeline(Config(), clients_csv=None, disabled="denylist")
    report = evaluate(corpus, [degraded])
    checks = check_thresholds(corpus, report, degraded)
    failed = {c.name for c in checks if not c.ok}
    assert "recall dictionary clients" in failed, [c.line() for c in checks]


def test_threshold_gate_does_not_pass_vacuously_on_empty_subset() -> None:
    """分類が消えて対象0件になったとき、黙って合格しないこと。"""
    empty = [Case(id="x", category="no-such-category", text="あ", entities=[])]
    report = evaluate(empty, [])
    checks = check_thresholds(empty, report, _FakeDetector())
    vacuous = [c for c in checks if "no cases" in c.name]
    assert vacuous and all(not c.ok for c in vacuous)


def test_harness_reports_perfect_for_ideal_detector() -> None:
    """ハーネス自己検証: 完全検出（gold 再生）なら 1.0 を返す。

    これは §10 の受け入れゲートではない（トートロジー）。実性能ゲートは
    test_pipeline_p3.py / test_pipeline_p4.py にある。ここは「ハーネスが完全検出
    に対して満点を出す」ことだけを確認し、指標計算経路の健全性を担保する。
    """
    corpus = load_corpus()
    rep = evaluate(corpus, [make_ideal_detector(corpus)])
    assert rep.recall == 1.0
    assert rep.exact_recall == 1.0
    assert rep.precision == 1.0
