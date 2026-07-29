"""LLM 検証パス — 追加専用の保険。

決定的マスク（＋NER）の**後段**に走る独立パス。精度の主役ではなく「辞書にも
ルールにも載らない未知固有名詞」を拾う保険。ローカル Ollama（localhost のみ）に
問い合わせ、**まだマスクされていない語だけ**を JSON で受け取り、スパンを**追加**
する。既存マスクの解除・変更は一切しない（不変条件§5 / ADR-005）。

fail-safe : Ollama 不在・タイムアウト・JSON パース失敗のいずれでも、その
チャンクの追加をスキップし決定的結果をそのまま採用する。原文に存在しない文字列は
破棄（幻覚防御）。LLM が返せるのは新規追加のみで、コードが構造的に「追加」に閉じる。
"""

from __future__ import annotations

import ipaddress
import json
import logging
import re
import urllib.error
import urllib.request
from urllib.parse import urlparse

from namemask.config import Config
from namemask.types import EntityType, Span

logger = logging.getLogger(__name__)

_ENABLED_DEFAULT = (EntityType.PERSON, EntityType.ORGANIZATION)
_MAX_SURFACE_LEN = 40  # 常識外に長い追加は幻覚/暴走とみなし捨てる
_MIN_SURFACE_LEN = 2


def _is_loopback_endpoint(endpoint: str) -> bool:
    """endpoint のホストがループバック（localhost / 127.0.0.0/8 / ::1）か判定する。

    ホスト名の DNS 解決はしない（解決自体が外部通信になり得るうえ、remote へ解決
    されるホスト名を許すと穴になる）。文字どおり localhost、またはループバック IP
    リテラルのみを許可する。
    """
    host = urlparse(endpoint).hostname
    if not host:
        return False
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False  # localhost 以外のホスト名 → 非ループバック扱い


class OllamaClient:
    """localhost の Ollama /api/generate を叩く最小クライアント（stdlib のみ）。

    生テキストのチャンクを POST するため、**エンドポイントは既定でループバックのみ**
    許可する（§9: このツール自体が漏洩源にならない）。ループバック以外を指定する
    には allow_remote=True を明示する必要がある（config: llm.allow_remote）。
    """

    def __init__(
        self, endpoint: str, model: str, timeout: float, allow_remote: bool = False
    ) -> None:
        if not allow_remote and not _is_loopback_endpoint(endpoint):
            raise ValueError(
                "LLM エンドポイントがループバック（localhost / 127.0.0.0/8 / ::1）では"
                f"ありません: {endpoint!r}。生テキストが外部へ送信されるのを防ぐため"
                "既定で拒否します。本当に外部LLMへ送る場合のみ config の "
                "llm.allow_remote: true を設定してください。"
            )
        self._url = endpoint.rstrip("/") + "/api/generate"
        self._model = model
        self._timeout = timeout

    def generate(self, prompt: str) -> str:
        """プロンプトを送り、モデルの応答テキスト（JSON文字列想定）を返す。

        失敗時は例外を送出（呼び出し側が fail-safe に握りつぶす）。
        """
        body = json.dumps({
            "model": self._model,
            "prompt": prompt,
            "stream": False,
            "format": "json",          # JSON 出力を強制
            "options": {"temperature": 0},
        }).encode("utf-8")
        req = urllib.request.Request(
            self._url, data=body, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=self._timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        return payload.get("response", "")


_FEWSHOT = (
    '例1（追加あり）:\n'
    '本文: 「先日オリオン企画と打ち合わせました。」\n'
    'すでにマスク済み: []\n'
    '出力: {"additions":[{"text":"オリオン企画","type":"ORGANIZATION"}]}\n\n'
    '例2（追加なし=空配列）:\n'
    '本文: 「本日は晴天なり。会議は延期します。」\n'
    'すでにマスク済み: []\n'
    '出力: {"additions":[]}\n\n'
    '例3（既存に触れない）:\n'
    '本文: 「[[組織_1]]の宮本さんから連絡がありました。」\n'
    'すでにマスク済み: ["宮本"]\n'
    '出力: {"additions":[]}\n\n'
)


def _build_prompt(chunk: str, existing: list[str]) -> str:
    existing_json = json.dumps(existing, ensure_ascii=False)
    return (
        "あなたは日本語文の匿名化支援です。まだマスクされていない、"
        "取引先・人物・案件を特定しうる固有名詞だけを列挙してください。\n"
        "厳守事項:\n"
        "- 追加分のみを JSON で返す。形式: "
        '{"additions":[{"text":"<原文にある語>","type":"PERSON|ORGANIZATION"}]}\n'
        "- 既にマスク済みの語や、一般名詞・地名・日付・数値は含めない。\n"
        "- 本文に一字一句存在する語だけを返す（存在しない語を作らない）。\n"
        "- 既存マスクの解除・変更はしない。\n\n"
        + _FEWSHOT
        + "本文: 「" + chunk + "」\n"
        + "すでにマスク済み: " + existing_json + "\n"
        + "出力:"
    )


def _map_type(raw: str | None) -> str:
    """LLM の型文字列を本ツール型へ。人物以外の固有名詞は ORGANIZATION に寄せる。"""
    if raw and ("PERSON" in raw.upper() or "人物" in raw or "人名" in raw):
        return EntityType.PERSON
    return EntityType.ORGANIZATION


def _parse_additions(raw_response: str) -> list[dict]:
    """モデル応答（JSON文字列）から additions 配列を取り出す。失敗は例外。"""
    data = json.loads(raw_response)
    if isinstance(data, list):
        return data
    items = data.get("additions", [])
    return items if isinstance(items, list) else []


class LlmVerifier:
    """追加専用の LLM 検証器。verify(text, existing) -> 追加スパン。"""

    name = "llm"

    def __init__(
        self,
        client: OllamaClient | None = None,
        *,
        chunk_chars: int = 700,
        enabled_types=_ENABLED_DEFAULT,
    ) -> None:
        self._client = client
        self._chunk_chars = max(200, chunk_chars)
        self._enabled = set(enabled_types)

    @classmethod
    def from_config(cls, config: Config, client: OllamaClient | None = None) -> "LlmVerifier":
        if client is None:
            # ループバック強制はここで効く（config.yaml に任意 URL を書いても
            # allow_remote: true が無い限り例外になる）。
            client = OllamaClient(
                endpoint=config.llm_endpoint,
                model=config.llm_model,
                timeout=config.llm_timeout_sec,
                allow_remote=config.llm_allow_remote,
            )
        return cls(client=client, chunk_chars=config.llm_chunk_chars)

    def _chunks(self, text: str) -> list[tuple[str, int]]:
        """文境界（。！？改行）で 500〜800 字程度に分割。offset を保持する。"""
        parts = re.split(r"(?<=[。！？\n])", text)
        chunks: list[tuple[str, int]] = []
        cur, start, pos = "", 0, 0
        for p in parts:
            if cur and len(cur) + len(p) > self._chunk_chars:
                chunks.append((cur, start))
                start, cur = pos, p
            else:
                cur += p
            pos += len(p)
        if cur:
            chunks.append((cur, start))
        return chunks

    def verify(self, text: str, existing_spans: list[Span]) -> list[Span]:
        if not text or self._client is None:
            return []
        additions: list[Span] = []
        for chunk, offset in self._chunks(text):
            end = offset + len(chunk)
            existing = sorted({
                text[s.start:s.end]
                for s in existing_spans
                if s.start < end and offset < s.end
            })
            prompt = _build_prompt(chunk, existing)
            try:
                raw = self._client.generate(prompt)
                items = _parse_additions(raw)
            except (urllib.error.URLError, OSError, ValueError, TimeoutError) as e:
                # Ollama 不在・タイムアウト・JSON 破損 → このチャンクは追加スキップ。
                logger.warning(
                    "LLM verify skipped for a chunk (%s); deterministic result kept.",
                    type(e).__name__,
                )
                continue
            additions.extend(self._spans_from_items(chunk, offset, items))
        return additions

    def _spans_from_items(self, chunk: str, offset: int, items: list) -> list[Span]:
        out: list[Span] = []
        for it in items:
            if not isinstance(it, dict):
                continue
            surface = it.get("text") or it.get("surface") or ""
            surface = surface.strip()
            if not (_MIN_SURFACE_LEN <= len(surface) <= _MAX_SURFACE_LEN):
                continue
            typ = _map_type(it.get("type"))
            if typ not in self._enabled:
                continue
            # 幻覚防御: chunk（＝原文の部分文字列）に実在する位置だけ採用。
            idx = chunk.find(surface)
            while idx != -1:
                start = offset + idx
                out.append(
                    Span(start, start + len(surface), typ,
                         score=0.4, sources=(self.name,))
                )
                idx = chunk.find(surface, idx + 1)
        return out
