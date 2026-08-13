"""評価基盤（Planv2 §8.2）— このツールの開発プロセスの心臓。

golden corpus に対してパイプラインを走らせ、エンティティ単位で
recall / precision / F1、型別 recall、検出層別の寄与、見逃し/誤検出明細を出す。
照合は partial（重なり）と exact（完全一致）の2段階。recall 判定は partial 基準。

P0/P1 時点では実検出器が未実装のため、既定では検出器なし（recall 0）で
「ハーネス自身の正しさ」を test_eval.py が合成検出器で検証する。
受け入れ基準の実運用判定は P3 以降で実検出器を差し込んで行う。
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

# 単体実行（python tests/eval.py）でも src/ を解決できるよう保険。
_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

# 上の sys.path 追加より後に import する必要がある（E402 は意図的）。
from namemask.detectors.base import Detector  # noqa: E402
from namemask.detectors.stub import GoldenStubDetector  # noqa: E402
from namemask.types import ALL_TYPES, Entity, Span  # noqa: E402

GOLDEN_DIR = Path(__file__).with_name("golden")
CORPUS_PATH = GOLDEN_DIR / "corpus.json"


@dataclass
class Case:
    id: str
    category: str
    text: str
    entities: list[Entity]
    note: str = ""


def load_corpus(path: Path | str = CORPUS_PATH) -> list[Case]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    cases = []
    for c in data:
        cases.append(
            Case(
                id=c["id"],
                category=c.get("category", ""),
                text=c["text"],
                entities=[Entity(e["surface"], e["type"], e.get("nth")) for e in c["entities"]],
                note=c.get("note", ""),
            )
        )
    return cases


def resolve_gold_spans(text: str, entities: list[Entity]) -> list[Span]:
    """正解エンティティを本文中の全出現スパンへ解決する。

    スタブ検出器と同じ解決規則（長い表層優先・非重複）を使い、
    「理想の検出」と golden 側を一致させる。
    """
    return GoldenStubDetector(entities).detect(text)


def run_detectors(text: str, detectors: list[Detector]) -> list[Span]:
    """全検出器を走らせて union（完全一致のみ重複除去）。"""
    spans: list[Span] = []
    seen: set[tuple[int, int, str, tuple[str, ...]]] = set()
    for det in detectors:
        for s in det.detect(text):
            key = (s.start, s.end, s.type, s.sources)
            if key not in seen:
                seen.add(key)
                spans.append(s)
    return spans


def _recall_hits(gold: list[Span], pred: list[Span], *, exact: bool) -> list[bool]:
    """各 gold スパンが pred に拾われたか（型一致必須）。"""
    hits = []
    for g in gold:
        if exact:
            hit = any(p.type == g.type and p.start == g.start and p.end == g.end for p in pred)
        else:
            hit = any(p.type == g.type and p.overlaps(g) for p in pred)
        hits.append(hit)
    return hits


def _precision_hits(gold: list[Span], pred: list[Span]) -> list[bool]:
    """各 pred スパンが正しい（型一致で gold と重なる）か。"""
    return [any(g.type == p.type and g.overlaps(p) for g in gold) for p in pred]


@dataclass
class EvalReport:
    n_cases: int
    gold_total: int
    pred_total: int
    tp_recall: int  # partial 基準で拾えた gold 数
    tp_precision: int  # gold と重なる pred 数
    exact_hits: int
    per_type_gold: dict[str, int] = field(default_factory=dict)
    per_type_hits: dict[str, int] = field(default_factory=dict)
    layer_contribution: dict[str, float] = field(default_factory=dict)
    false_negatives: list[tuple[str, str, str]] = field(default_factory=list)
    false_positives: list[tuple[str, str, str]] = field(default_factory=list)

    @property
    def recall(self) -> float:
        return self.tp_recall / self.gold_total if self.gold_total else 1.0

    @property
    def precision(self) -> float:
        return self.tp_precision / self.pred_total if self.pred_total else 1.0

    @property
    def f1(self) -> float:
        r, p = self.recall, self.precision
        return 2 * p * r / (p + r) if (p + r) else 0.0

    @property
    def exact_recall(self) -> float:
        return self.exact_hits / self.gold_total if self.gold_total else 1.0

    def type_recall(self, type_: str) -> float:
        g = self.per_type_gold.get(type_, 0)
        return self.per_type_hits.get(type_, 0) / g if g else 1.0

    def category_recall(self, cases: list[Case]) -> dict[str, tuple[int, int]]:
        raise NotImplementedError  # 予約（P3 で層別と併用）

    def summary(self, include_layer_contribution: bool = True) -> str:
        lines = [
            f"cases={self.n_cases} gold={self.gold_total} pred={self.pred_total}",
            f"recall(partial)={self.recall:.4f} precision={self.precision:.4f} f1={self.f1:.4f}",
            f"exact_recall={self.exact_recall:.4f}",
            "per-type recall:",
        ]
        for t in ALL_TYPES:
            if self.per_type_gold.get(t):
                lines.append(
                    f"  {t:12s} {self.type_recall(t):.4f} "
                    f"({self.per_type_hits.get(t, 0)}/{self.per_type_gold[t]})"
                )
        # source ベースの層別寄与は「各検出器が別々の source を持つ」前提でのみ
        # 正しい。統合済み PipelineDetector では無意味（真の値は
        # evaluate_layer_contribution を使う）。既定では出すが __main__ は抑止する。
        if include_layer_contribution and self.layer_contribution:
            lines.append("layer contribution (recall drop if removed):")
            for name, drop in sorted(self.layer_contribution.items(), key=lambda kv: -kv[1]):
                lines.append(f"  {name:12s} -{drop:.4f}")
        if self.false_negatives:
            lines.append(f"false negatives ({len(self.false_negatives)}):")
            for cid, surf, t in self.false_negatives[:50]:
                lines.append(f"  [{cid}] {t}: {surf!r}")
        if self.false_positives:
            lines.append(f"false positives ({len(self.false_positives)}):")
            for cid, surf, t in self.false_positives[:50]:
                lines.append(f"  [{cid}] {t}: {surf!r}")
        return "\n".join(lines)


def evaluate(cases: list[Case], detectors: list[Detector]) -> EvalReport:
    gold_total = pred_total = tp_recall = tp_precision = exact_hits = 0
    per_type_gold: dict[str, int] = defaultdict(int)
    per_type_hits: dict[str, int] = defaultdict(int)
    false_negatives: list[tuple[str, str, str]] = []
    false_positives: list[tuple[str, str, str]] = []

    # 層別寄与のため、層を1つ抜いた時の recall 低下を測る。
    layer_names = sorted({d.name for d in detectors})
    tp_without: dict[str, int] = defaultdict(int)  # 層 name を抜いた時に拾えた gold 数

    for case in cases:
        gold = resolve_gold_spans(case.text, case.entities)
        pred = run_detectors(case.text, detectors)

        gold_total += len(gold)
        pred_total += len(pred)

        r_hits = _recall_hits(gold, pred, exact=False)
        e_hits = _recall_hits(gold, pred, exact=True)
        p_hits = _precision_hits(gold, pred)

        tp_recall += sum(r_hits)
        exact_hits += sum(e_hits)
        tp_precision += sum(p_hits)

        # _recall_hits / _precision_hits は入力と同じ長さのリストを返す（strict で担保）。
        for g, hit in zip(gold, r_hits, strict=True):
            per_type_gold[g.type] += 1
            if hit:
                per_type_hits[g.type] += 1
            else:
                false_negatives.append((case.id, g.surface(case.text), g.type))

        for p, hit in zip(pred, p_hits, strict=True):
            if not hit:
                false_positives.append((case.id, p.surface(case.text), p.type))

        # 層別寄与
        for name in layer_names:
            pred_wo = [p for p in pred if name not in p.sources]
            r_wo = _recall_hits(gold, pred_wo, exact=False)
            tp_without[name] += sum(r_wo)

    layer_contribution: dict[str, float] = {}
    if gold_total:
        full_recall = tp_recall / gold_total
        for name in layer_names:
            layer_contribution[name] = full_recall - tp_without[name] / gold_total

    return EvalReport(
        n_cases=len(cases),
        gold_total=gold_total,
        pred_total=pred_total,
        tp_recall=tp_recall,
        tp_precision=tp_precision,
        exact_hits=exact_hits,
        per_type_gold=dict(per_type_gold),
        per_type_hits=dict(per_type_hits),
        layer_contribution=layer_contribution,
        false_negatives=false_negatives,
        false_positives=false_positives,
    )


def evaluate_layer_contribution(
    cases: list[Case],
    pipeline_factory,
    layer_names,
) -> tuple[EvalReport, dict[str, float]]:
    """層別寄与を「真のアブレーション」で測る（Planv2 §8.2 / P3.5-4）。

    merge 後の sources からスパンを除外する方式は boundary/propagation が他層
    由来のため正しくない。代わりに層を1つ無効化したパイプラインを再構成して
    再評価し、full との recall 差を寄与とする。

    pipeline_factory(disabled) は disabled 層（None=全層）を抜いた Detector を返す。
    """
    full = evaluate(cases, [pipeline_factory(None)])
    contribution: dict[str, float] = {}
    for layer in layer_names:
        without = evaluate(cases, [pipeline_factory(layer)])
        contribution[layer] = full.recall - without.recall
    return full, contribution


def make_ideal_detector(cases: list[Case]) -> Detector:
    """P1 用の理想検出器（スタブ=gold）。

    本文 -> そのケースの正解エンティティを引き、全出現を拾う。
    ハーネスの数値経路（partial/exact/型別/層別）を既知の完全検出で検証する。
    """
    index: dict[str, list[Entity]] = {}
    for c in cases:
        index.setdefault(c.text, []).extend(c.entities)

    class _Ideal:
        name = "stub"

        def detect(self, text: str) -> list[Span]:
            return GoldenStubDetector(index.get(text, [])).detect(text)

    return _Ideal()


# --- 受け入れ基準（CLAUDE.md §6 の表）------------------------------------
#
# **ここが閾値の単一の真実の源。** テスト（tests/test_pipeline_p3.py）も CI の
# eval ジョブも、この定数を参照する。数値を下げる変更を入れないこと。
#
# 表のうち round-trip 完全一致・同一表記の文書内一貫性は、スパン集合ではなく
# 置換/復元の性質なので eval では測らない（tests/test_golden.py が担保する）。

#: 法人格を含む組織名のケース分類（≥98% を要求する対象）。
LEGAL_FORM_CATEGORIES = frozenset(
    {"org-prefix", "org-suffix", "org-abbr", "org-glyph", "org-fullwidth"}
)
#: 辞書登録済み取引先のケース分類（100% を要求する対象）。
DICTIONARY_CATEGORIES = frozenset({"org-core", "dict-variant"})
#: 正規表現層が 100% を要求される型。
REGEX_TYPES = ("EMAIL", "PHONE", "MYNUMBER")

MIN_OVERALL_RECALL = 0.95
MIN_OVERALL_PRECISION = 0.70
MIN_LEGAL_FORM_ORG_RECALL = 0.98
MIN_DICTIONARY_RECALL = 1.0
MIN_REGEX_RECALL = 1.0


@dataclass
class ThresholdCheck:
    name: str
    measured: float
    threshold: float

    @property
    def ok(self) -> bool:
        return self.measured >= self.threshold

    def line(self) -> str:
        mark = "OK  " if self.ok else "FAIL"
        return f"  [{mark}] {self.name:34s} {self.measured:.4f} >= {self.threshold:.4f}"


def check_thresholds(
    cases: list[Case], report: EvalReport, detector: Detector
) -> list[ThresholdCheck]:
    """受け入れ基準を実測値と突き合わせる。判定は呼び出し側（ok の全 and）。"""
    checks = [
        ThresholdCheck("overall recall (partial)", report.recall, MIN_OVERALL_RECALL),
        ThresholdCheck("overall precision", report.precision, MIN_OVERALL_PRECISION),
    ]
    for t in REGEX_TYPES:
        checks.append(
            ThresholdCheck(f"recall {t.lower()}", report.type_recall(t), MIN_REGEX_RECALL)
        )

    subsets = (
        ("recall dictionary clients", DICTIONARY_CATEGORIES, MIN_DICTIONARY_RECALL),
        ("recall org with legal form", LEGAL_FORM_CATEGORIES, MIN_LEGAL_FORM_ORG_RECALL),
    )
    for name, categories, threshold in subsets:
        subset = [c for c in cases if c.category in categories]
        if not subset:
            # 分類が消えたのに気付かず「該当0件だから合格」になるのを防ぐ。
            checks.append(ThresholdCheck(f"{name} (no cases!)", 0.0, threshold))
            continue
        sub_report = evaluate(subset, [detector])
        checks.append(ThresholdCheck(name, sub_report.type_recall("ORGANIZATION"), threshold))
    return checks


def _run_cli() -> None:
    """実パイプラインの実測と真のアブレーション（層別 recall 寄与）を表示する。

    使い方: python tests/eval.py [--ner] [--address] [--assert-thresholds]
    """
    import argparse

    from namemask.config import Config
    from namemask.pipeline.build import ALL_LAYER_NAMES, make_pipeline

    ap = argparse.ArgumentParser(description="実パイプラインの eval を表示")
    ap.add_argument("--ner", action="store_true", help="NER 層を有効化して評価")
    ap.add_argument("--address", action="store_true", help="住所層（P7）を有効化して評価")
    ap.add_argument(
        "--clients",
        default=str(GOLDEN_DIR / "clients_test.csv"),
        help="取引先マスタ CSV",
    )
    ap.add_argument(
        "--assert-thresholds",
        action="store_true",
        help="受け入れ基準（CLAUDE.md §6）を検査し、下回ったら非ゼロ終了する（CI ゲート）",
    )
    args = ap.parse_args()

    corpus = load_corpus()
    cfg = Config()

    def factory(disabled: str | None = None):
        return make_pipeline(
            cfg,
            args.clients,
            disabled=disabled,
            use_ner=args.ner,
            use_address=args.address,
        )

    layer_names = (
        ALL_LAYER_NAMES + (("address",) if args.address else ()) + (("ner",) if args.ner else ())
    )
    full, contrib = evaluate_layer_contribution(corpus, factory, layer_names)

    opts = [s for s, on in (("NER on", args.ner), ("address on", args.address)) if on]
    header = "実パイプライン" + (
        f"（{' / '.join(opts)}）" if opts else "（NER off / 決定的層のみ）"
    )
    print(f"=== {header} ===")
    # source ベースの誤解を招く行は抑止し、真のアブレーションを別途出す。
    print(full.summary(include_layer_contribution=False))
    print("\n=== 真のアブレーション: 層を外した時の recall 低下 ===")
    for name, drop in sorted(contrib.items(), key=lambda kv: -kv[1]):
        print(f"  {name:12s} -{drop:.4f}")

    if args.assert_thresholds:
        checks = check_thresholds(corpus, full, factory(None))
        print("\n=== 受け入れ基準（CLAUDE.md §6）===")
        for c in checks:
            print(c.line())
        failed = [c for c in checks if not c.ok]
        if failed:
            names = ", ".join(c.name for c in failed)
            print(f"\n閾値を下回りました: {names}", file=sys.stderr)
            raise SystemExit(1)
        print("\nすべての閾値を満たしています。")


if __name__ == "__main__":
    _run_cli()
