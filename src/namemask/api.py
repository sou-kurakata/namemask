"""高レベル API。CLI・将来のレビューUI が共通で使う入口。

mask_text: 検出パイプライン → スパン統合 → 置換 を一気通貫で行う。
unmask_text: mapping による復元。
"""

from __future__ import annotations

from pathlib import Path

from namemask.config import Config, load_config
from namemask.core import mask as _mask
from namemask.core import unmask as _unmask
from namemask.pipeline.build import build_default_pipeline, build_verifier, run_pipeline
from namemask.types import MaskResult, RestoreResult


def mask_text(
    text: str,
    *,
    config: Config | None = None,
    clients_csv: str | Path | None = None,
    use_ner: bool = True,
    use_llm: bool = False,
    use_address: bool = False,
    llm_client=None,
) -> MaskResult:
    """テキストを検出・仮名化して MaskResult を返す。

    use_ner=True でも GiNZA 未導入なら NER は fail-safe に無効化され、決定的層
    のみで動く。use_llm=True で LLM 検証パスを
    後段に付ける。use_address=True で住所層を有効化する。
    """
    cfg = config or load_config()
    detectors = build_default_pipeline(
        cfg,
        clients_csv,
        use_ner=use_ner,
        use_address=use_address,
    )
    verifier = build_verifier(cfg, use_llm=use_llm, client=llm_client)
    spans = run_pipeline(text, detectors, verifier)
    return _mask(text, spans)


def unmask_text(text: str, mapping: dict[str, str]) -> RestoreResult:
    """外部AI応答のプレースホルダを mapping で復元する。"""
    return _unmask(text, mapping)
