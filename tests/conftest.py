"""pytest 共通設定・フィクスチャ。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# pyproject の pythonpath が効かない環境でも src/ を解決できるよう保険。
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from eval import Case, load_corpus  # noqa: E402


@pytest.fixture(scope="session")
def corpus() -> list[Case]:
    return load_corpus()


@pytest.fixture(scope="session")
def clients_csv() -> str:
    return str(Path(__file__).parent / "golden" / "clients_test.csv")


@pytest.fixture(scope="session")
def pipeline(clients_csv: str):
    """P3 決定的検出パイプライン（辞書＝テスト用取引先マスタ）。"""
    from namemask.config import Config
    from namemask.pipeline.build import PipelineDetector, build_default_pipeline

    return PipelineDetector(build_default_pipeline(Config(), clients_csv=clients_csv))
