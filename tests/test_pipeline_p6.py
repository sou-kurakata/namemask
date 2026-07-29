"""P6 受け入れ（Planv2 §7 / §11 P6）— LLM 検証パスの on/off recall 差。

未知固有名詞（法人格なし・辞書外）を決定的層は取りこぼす。LLM 検証パス（追加専用）
を後段に付けると拾えることを、モック LLM で決定的に確認する。実 Ollama を使う
統合テストは reachable なときだけ実行する。
"""

from __future__ import annotations

import socket

import pytest

from eval import Case, evaluate
from namemask.config import Config
from namemask.core import mask, unmask
from namemask.pipeline.build import make_pipeline
from namemask.types import EntityType
from test_llm_verifier import FakeClient

_UNKNOWN = [
    {"text": "オリオン企画", "type": "ORGANIZATION"},
    {"text": "ネビュラ物流", "type": "ORGANIZATION"},
]


@pytest.fixture(scope="module")
def unknown_cases(corpus: list[Case]) -> list[Case]:
    return [c for c in corpus if c.category == "unknown-entity"]


def test_deterministic_misses_unknown_entities(unknown_cases, clients_csv: str) -> None:
    off = make_pipeline(Config(), clients_csv)  # 決定的層のみ
    rep = evaluate(unknown_cases, [off])
    assert rep.type_recall(EntityType.ORGANIZATION) < 1.0


def test_llm_recovers_unknown_entities(unknown_cases, clients_csv: str) -> None:
    on = make_pipeline(Config(), clients_csv, llm_client=FakeClient(_UNKNOWN))
    rep = evaluate(unknown_cases, [on])
    assert rep.type_recall(EntityType.ORGANIZATION) == 1.0, rep.summary()


def test_llm_on_off_recall_gain(unknown_cases, clients_csv: str) -> None:
    off = evaluate(unknown_cases, [make_pipeline(Config(), clients_csv)])
    on = evaluate(unknown_cases,
                  [make_pipeline(Config(), clients_csv, llm_client=FakeClient(_UNKNOWN))])
    assert on.recall > off.recall


def test_llm_additions_roundtrip(unknown_cases, clients_csv: str) -> None:
    on = make_pipeline(Config(), clients_csv, llm_client=FakeClient(_UNKNOWN))
    for case in unknown_cases:
        spans = on.detect(case.text)
        m = mask(case.text, spans)
        r = unmask(m.masked_text, m.mapping)
        assert r.text == case.text, f"[{case.id}] round-trip failed"


def test_llm_is_additive_only(clients_csv: str) -> None:
    """LLM は既存の決定的スパンを消さない（追加専用・ADR-005）。"""
    text = "株式会社アオヤマ商事とオリオン企画が提携。"
    det = make_pipeline(Config(), clients_csv)
    llm = make_pipeline(Config(), clients_csv, llm_client=FakeClient(_UNKNOWN))
    det_surfaces = {text[s.start:s.end] for s in det.detect(text)}
    llm_surfaces = {text[s.start:s.end] for s in llm.detect(text)}
    # 決定的で拾えた社名は LLM 有効でも残り、かつオリオン企画が増える。
    assert det_surfaces <= llm_surfaces
    assert "オリオン企画" in llm_surfaces


# --- 実 Ollama がある場合のみの統合スモーク ---

def _ollama_reachable(host: str = "127.0.0.1", port: int = 11434) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.3):
            return True
    except OSError:
        return False


@pytest.mark.skipif(not _ollama_reachable(), reason="Ollama (localhost:11434) が無い")
def test_real_ollama_smoke(clients_csv: str) -> None:
    # 実 Ollama があれば、例外を投げず（fail-safe 含む）動作すること・round-trip のみ確認。
    on = make_pipeline(Config(), clients_csv, use_llm=True)
    text = "先日、オリオン企画と新規の取引を開始しました。"
    spans = on.detect(text)
    m = mask(text, spans)
    assert unmask(m.masked_text, m.mapping).text == text
