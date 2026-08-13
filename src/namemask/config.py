"""設定ローダ（config.yaml）。

config.yaml が無い/一部欠落でも安全な既定値で動くようにする。
検出器は config オブジェクトを受け取り、閾値・パターン・辞書パスを引く。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from namemask import paths


@dataclass
class Config:
    raw: dict[str, Any] = field(default_factory=dict)

    def section(self, name: str) -> dict[str, Any]:
        val = self.raw.get(name)
        return val if isinstance(val, dict) else {}

    # --- よく使う値のアクセサ（既定値込み）---
    @property
    def person_max_len(self) -> int:
        return int(self.section("structural").get("person_max_len", 4))

    @property
    def person_stopwords(self) -> list[str]:
        return list(
            self.section("structural").get(
                "person_stopwords", ["皆", "みな", "お客", "客", "奥", "各位"]
            )
        )

    @property
    def org_name_max_len(self) -> int:
        return int(self.section("structural").get("org_name_max_len", 24))

    @property
    def denylist_min_core_len(self) -> int:
        return int(self.section("denylist").get("min_core_len", 3))

    @property
    def clients_csv(self) -> str | None:
        return self.section("denylist").get("clients_csv")

    @property
    def persons_csv(self) -> str | None:
        return self.section("denylist").get("persons_csv")

    @property
    def regex_extra_patterns(self) -> list[dict[str, Any]]:
        return list(self.section("regex").get("extra_patterns", []))

    # --- LLM 検証パス（任意）---
    @property
    def llm_enabled(self) -> bool:
        return bool(self.section("llm").get("enabled", False))

    @property
    def llm_endpoint(self) -> str:
        return str(self.section("llm").get("endpoint", "http://localhost:11434"))

    @property
    def llm_model(self) -> str:
        return str(self.section("llm").get("model", "qwen2.5-coder:7b"))

    @property
    def llm_chunk_chars(self) -> int:
        return int(self.section("llm").get("chunk_chars", 700))

    @property
    def llm_timeout_sec(self) -> float:
        return float(self.section("llm").get("timeout_sec", 30))

    @property
    def llm_allow_remote(self) -> bool:
        # 既定 False: 生テキストを外部へ送らないため endpoint はループバック限定。
        return bool(self.section("llm").get("allow_remote", False))

    # --- セキュリティ（Planv3 §5。口だけ用意）---
    @property
    def encrypt_by_default(self) -> bool:
        # 共用PC運用時に mapping 保存を既定で暗号化するか。情シス確認事項（§10）。
        return bool(self.section("security").get("encrypt_by_default", False))


def load_config(path: Path | str | None = None) -> Config:
    """config.yaml を読み込む。既定パスは呼び出し時に解決する（ADR-106）。

    ファイルが無くても安全な既定値で動く。**書き出しの副作用は持たない**
    （雛形書き出しは :func:`ensure_config_file`。ADR-107）。
    """
    target = Path(path) if path is not None else paths.config_path()
    if not target.exists():
        return Config(raw={})
    data = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    return Config(raw=data if isinstance(data, dict) else {})


# 非エンジニアが情シス指定値へ書き換えるだけで済む、日本語コメント入りの雛形。
# 値は Config の各アクセサ既定と一致させること（雛形が実装と食い違わないように）。
_CONFIG_TEMPLATE = """\
# namemask 設定ファイル（自動生成された雛形）。
# 情シスの指定に合わせて値を書き換えてください。行頭 # はコメントです。
# このファイルは %LOCALAPPDATA%\\namemask\\config.yaml に置かれます。

# --- 辞書層（取引先マスタ）---
denylist:
  # 取引先マスタCSVのパス。配布物には同梱しません（機密のため）。
  # 共有フォルダのUNCパスを指定してください。例: \\\\server\\tools\\namemask\\clients.csv
  # 読めない場合は辞書層なしで起動し、画面に1行だけ警告を出します（起動は止めません）。
  clients_csv: null
  persons_csv: null          # 人名マスタ（任意）
  min_core_len: 3            # コア名2文字以下は法人格付きのみ照合（誤検出の安全弁）

# --- 構造ルール層 ---
structural:
  person_max_len: 4          # 敬称の直前で人名候補とする最大文字数
  person_stopwords: [皆, みな, お客, 客, 奥, 各位]
  org_name_max_len: 24

# --- 正規表現層（追加パターンの口）---
regex:
  extra_patterns: []         # 例: [{name: CASE_CODE, type: ORGANIZATION, pattern: '...'}]

# --- LLM検証パス（初版ビルドでは非同梱・既定オフ）---
llm:
  enabled: false
  endpoint: http://localhost:11434   # ループバック限定。外部へは送りません。
  allow_remote: false        # true にしない限り生テキストは外部へ出しません。
  model: qwen2.5-coder:7b
  chunk_chars: 700
  timeout_sec: 30

# --- セキュリティ ---
security:
  # 共用PCで mapping 保存を既定で暗号化するか。情シスと相談のうえ設定してください。
  encrypt_by_default: false
"""


def default_config_template() -> str:
    """config.yaml の雛形（日本語コメント入り）を文字列で返す。"""
    return _CONFIG_TEMPLATE


def ensure_config_file(path: Path | str | None = None) -> Path:
    """config.yaml が無ければ日本語コメント入りの雛形を書き出す（Planv3 §5）。

    既存ファイルは上書きしない。既定パスは呼び出し時に解決する（ADR-106）。
    load_config の副作用にはせず、アプリ起動時に明示的に呼ぶこと（ADR-107）。
    """
    target = Path(path) if path is not None else paths.config_path()
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(_CONFIG_TEMPLATE, encoding="utf-8")
    return target
