"""LLM 検証パスの単体テスト（Planv2 §7）— 実 Ollama 不要（クライアント注入）。

追加専用・幻覚防御・fail-safe・チャンク offset・型マッピングを、モック
クライアントで決定的に検証する。
"""

from __future__ import annotations

import json

import pytest

from namemask.config import Config
from namemask.detectors.llm_verifier import (
    LlmVerifier,
    OllamaClient,
    _is_loopback_endpoint,
)
from namemask.types import EntityType


class FakeClient:
    """generate() が固定の additions（or 例外）を返すモック。"""

    def __init__(self, additions: list[dict] | None = None, raise_exc: Exception | None = None):
        self._additions = additions or []
        self._raise = raise_exc

    def generate(self, prompt: str) -> str:
        if self._raise is not None:
            raise self._raise
        return json.dumps({"additions": self._additions})


# ---- エンドポイントのループバック強制（§9・生テキスト外部送信の防止）----

def test_is_loopback_endpoint() -> None:
    for ok in ["http://localhost:11434", "http://127.0.0.1:11434",
               "http://127.0.0.5", "http://[::1]:11434"]:
        assert _is_loopback_endpoint(ok), ok
    for bad in ["http://evil.example.com:11434", "http://10.0.0.5:11434",
                "http://169.254.1.1", "https://api.openai.com"]:
        assert not _is_loopback_endpoint(bad), bad


def test_ollama_client_rejects_remote_by_default() -> None:
    with pytest.raises(ValueError):
        OllamaClient(endpoint="http://evil.example.com:11434", model="m", timeout=5)
    # ループバックは通る
    OllamaClient(endpoint="http://127.0.0.1:11434", model="m", timeout=5)


def test_ollama_client_allow_remote_override() -> None:
    # 明示的に許可した場合のみ非ループバックを受け付ける。
    OllamaClient(endpoint="http://10.0.0.5:11434", model="m", timeout=5,
                 allow_remote=True)


def test_from_config_rejects_remote_endpoint() -> None:
    cfg = Config(raw={"llm": {"endpoint": "http://evil.example.com:11434"}})
    with pytest.raises(ValueError):
        LlmVerifier.from_config(cfg)
    # allow_remote: true なら許可
    cfg2 = Config(raw={"llm": {"endpoint": "http://evil.example.com:11434",
                               "allow_remote": True}})
    LlmVerifier.from_config(cfg2)


def test_from_config_default_localhost_ok() -> None:
    LlmVerifier.from_config(Config())  # 既定 localhost → 例外なし


def test_chunks_preserve_text_and_offsets() -> None:
    v = LlmVerifier(client=FakeClient(), chunk_chars=200)
    text = "".join(f"これは{i}番目の文です。" for i in range(40))
    chunks = v._chunks(text)
    assert "".join(c for c, _ in chunks) == text
    for chunk, offset in chunks:
        assert text[offset:offset + len(chunk)] == chunk


def test_verify_adds_span_for_present_entity() -> None:
    text = "先日、オリオン企画と契約しました。"
    v = LlmVerifier(client=FakeClient([{"text": "オリオン企画", "type": "ORGANIZATION"}]))
    spans = v.verify(text, existing_spans=[])
    assert len(spans) == 1
    s = spans[0]
    assert s.type == EntityType.ORGANIZATION
    assert text[s.start:s.end] == "オリオン企画"
    assert s.sources == ("llm",)


def test_verify_discards_hallucination() -> None:
    # 原文に存在しない語は破棄（幻覚防御）。
    text = "本日は特筆事項なし。"
    v = LlmVerifier(client=FakeClient([{"text": "架空商事", "type": "ORGANIZATION"}]))
    assert v.verify(text, []) == []


def test_verify_failsafe_on_client_error() -> None:
    # Ollama 不在・タイムアウト等 → 例外を握りつぶして [] を返す。
    text = "オリオン企画と契約。"
    v = LlmVerifier(client=FakeClient(raise_exc=ConnectionError("refused")))
    assert v.verify(text, []) == []


def test_verify_no_client_returns_empty() -> None:
    assert LlmVerifier(client=None).verify("オリオン企画", []) == []


def test_verify_type_mapping_person_and_default_org() -> None:
    text = "山本ソフィアと未来案件について話した。"
    v = LlmVerifier(client=FakeClient([
        {"text": "山本ソフィア", "type": "人物"},
        {"text": "未来案件", "type": "案件"},   # 非人物 → ORGANIZATION に寄せる
    ]))
    got = {(s.type, text[s.start:s.end]) for s in v.verify(text, [])}
    assert (EntityType.PERSON, "山本ソフィア") in got
    assert (EntityType.ORGANIZATION, "未来案件") in got


def test_verify_length_guards() -> None:
    text = "Aと" + "超" * 50 + "社について。"
    v = LlmVerifier(client=FakeClient([
        {"text": "A", "type": "ORGANIZATION"},          # 短すぎ → 捨てる
        {"text": "超" * 50, "type": "ORGANIZATION"},     # 長すぎ → 捨てる
    ]))
    assert v.verify(text, []) == []


def test_verify_finds_all_occurrences() -> None:
    text = "オリオン企画。再度オリオン企画に連絡。"
    v = LlmVerifier(client=FakeClient([{"text": "オリオン企画", "type": "ORGANIZATION"}]))
    spans = v.verify(text, [])
    assert len(spans) == 2
    assert all(text[s.start:s.end] == "オリオン企画" for s in spans)
