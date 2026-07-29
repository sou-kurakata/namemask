"""パイプライン組み立て。

決定的検出層（正規表現・構造ルール・辞書）を影テキスト上で走らせ、原文座標へ
逆変換し、スパン統合層でまとめる。NER以降はここに union 追加していく。
"""

from __future__ import annotations

from pathlib import Path

from namemask.config import Config, load_config
from namemask.detectors.base import Detector
from namemask.detectors.address_ja import AddressDetector
from namemask.detectors.denylist import DenylistDetector, load_clients_csv
from namemask.detectors.llm_verifier import LlmVerifier
from namemask.detectors.ner import NerDetector
from namemask.detectors.normalizing import (
    FoldNormalizingDetector,
    NormalizingDetector,
)
from namemask.detectors.regex_ja import RegexDetector
from namemask.detectors.structural_ja import StructuralDetector
from namemask.pipeline.merger import merge_spans
from namemask.types import Span


def build_default_pipeline(
    config: Config | None = None,
    clients_csv: str | Path | None = None,
    layers: set[str] | None = None,
    use_ner: bool = False,
    use_address: bool = False,
) -> list[Detector]:
    """検出層（原文座標を返す Detector 群）を組み立てる。

    clients_csv を明示指定した場合はそれを辞書に使う（テスト用）。省略時は
    config の denylist.clients_csv を参照する。
    layers を渡すと、その層名（regex/structural/denylist/ner/address）だけを
    組み込む（eval の層別アブレーション用）。
    use_ner=True で NER 層（GiNZA）、use_address=True で住所層を追加する。
    追加系は決定的層の精度検証に影響させないため既定は無効。
    """
    cfg = config or load_config()

    # 正規表現・構造ルールは NFKC 影、辞書は fold 影で照合する。
    regex = NormalizingDetector(RegexDetector(cfg))
    structural = NormalizingDetector(StructuralDetector(cfg))

    if clients_csv is not None and Path(clients_csv).exists():
        rows = load_clients_csv(clients_csv)
        denylist = FoldNormalizingDetector(
            DenylistDetector(rows, min_core_len=cfg.denylist_min_core_len)
        )
    else:
        denylist = FoldNormalizingDetector(DenylistDetector.from_config(cfg))

    all_layers: dict[str, Detector] = {
        "regex": regex, "structural": structural, "denylist": denylist,
    }
    if use_address:
        all_layers["address"] = NormalizingDetector(AddressDetector())
    if use_ner:
        all_layers["ner"] = NerDetector.from_config(cfg)

    selected = all_layers if layers is None else {
        name: det for name, det in all_layers.items() if name in layers
    }
    return list(selected.values())


def run_pipeline(
    text: str,
    detectors: list[Detector],
    verifier: LlmVerifier | None = None,
) -> list[Span]:
    """全検出器を走らせ、スパン統合層で確定スパンにする。

    verifier（LLM 検証パス）を渡すと、決定的（＋NER）統合の**後段**で
    追加スパンだけを受け取り、もう一度統合する。
    """
    raw: list[Span] = []
    for det in detectors:
        raw.extend(det.detect(text))
    merged = merge_spans(text, raw)
    if verifier is not None:
        additions = verifier.verify(text, merged)
        if additions:
            merged = merge_spans(text, merged + additions)
    return merged


ALL_LAYER_NAMES: tuple[str, ...] = ("regex", "structural", "denylist")


def build_verifier(
    config: Config | None = None,
    use_llm: bool = False,
    client=None,
) -> LlmVerifier | None:
    """LLM 検証パスを組み立てる。use_llm=False なら None（無効）。

    client を注入するとテストで実 Ollama 無しに動かせる。
    """
    if not use_llm and client is None:
        return None
    cfg = config or load_config()
    return LlmVerifier.from_config(cfg, client=client)


def make_pipeline(
    config: Config | None = None,
    clients_csv: str | Path | None = None,
    disabled: str | None = None,
    use_ner: bool = False,
    use_llm: bool = False,
    use_address: bool = False,
    llm_client=None,
) -> "PipelineDetector":
    """層を1つ無効化できるパイプライン工場（eval のアブレーション用）。

    disabled に層名（regex/structural/denylist/ner/address/llm）を渡すとその層を除く。
    use_llm=True または llm_client 注入で LLM 検証パスを後段に付ける。
    """
    names = (
        ALL_LAYER_NAMES
        + (("address",) if use_address else ())
        + (("ner",) if use_ner else ())
    )
    layers = set(names) - ({disabled} if disabled else set())
    detectors = build_default_pipeline(
        config, clients_csv, layers=layers, use_ner=use_ner, use_address=use_address,
    )
    want_llm = (use_llm or llm_client is not None) and disabled != "llm"
    verifier = build_verifier(config, use_llm=want_llm, client=llm_client)
    return PipelineDetector(detectors, verifier=verifier)


class PipelineDetector:
    """複数検出器＋統合層（＋任意で LLM 検証パス）を1つの Detector に見せる。

    eval はこれを単一検出器として扱う。統合後スパンは sources に各層名を
    保持するため、層別寄与の計測（eval）も機能する。
    """

    name = "pipeline"

    def __init__(
        self, detectors: list[Detector], verifier: LlmVerifier | None = None
    ) -> None:
        self._detectors = detectors
        self._verifier = verifier

    def detect(self, text: str) -> list[Span]:
        return run_pipeline(text, self._detectors, self._verifier)
