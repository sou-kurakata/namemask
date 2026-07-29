"""アプリのデータディレクトリとパス解決を一元化する（Planv3 §5 / N3）。

凍結ビルド（PyInstaller onedir）では cwd / __file__ が信頼できない:
- ``__file__`` は ``sys._MEIPASS`` 配下（読み取り専用の一時展開先）になり編集不能。
- cwd はスタートメニュー/ショートカット起動で不定（``C:\\Windows\\System32`` に
  なり得る）。そこへ mapping（生の機密）を書けば事故になる。

そのため書き込み先は常に :func:`app_data_dir` を単一の真実の源として解決する。
既定値は **import 時ではなく呼び出し時** に評価する（凍結判定・環境変数を実行時に
反映するため。config.py / mapping.py / cli.py はこの方針に従う。ADR-106）。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "namemask"


def is_frozen() -> bool:
    """PyInstaller 等で凍結されたビルドかどうか。"""
    return bool(getattr(sys, "frozen", False))


def app_data_dir() -> Path:
    """設定・mapping・ログを置く、書き込み可能なベースディレクトリ。

    - 凍結時: ``%LOCALAPPDATA%\\namemask``（cwd / __file__ に依存しない）。
      ``LOCALAPPDATA`` が無い異常時のみユーザーホーム配下へフォールバックする
      （いずれにせよ cwd / System32 には書かない、が N3 の要点）。
    - 開発時: カレントディレクトリ（Planv2 の現行動作を維持）。

    **副作用なし（純関数）**: ディレクトリは作らない。作成は書き込み時
    （`MappingStore.save` / `ensure_config_file`）に限る（ADR-106 M0 補足）。
    """
    if is_frozen():
        local = os.environ.get("LOCALAPPDATA")
        base = (Path(local) if local else Path.home()) / APP_NAME
    else:
        base = Path(".")
    return base


def config_path() -> Path:
    """config.yaml の既定パス。

    - 凍結時: ``app_data_dir()/config.yaml``（情シスが編集できるよう可変領域へ）。
    - 開発時: **リポジトリ同梱の config.yaml**（``__file__`` 起点。cwd に依らず
      同梱設定を読む Planv2 の挙動を維持。ADR-106 M0 補足）。
    """
    if is_frozen():
        return app_data_dir() / "config.yaml"
    # src/namemask/paths.py → parents[2] = リポジトリルート。
    return Path(__file__).resolve().parents[2] / "config.yaml"


def session_dir() -> Path:
    """mapping 等セッション機密の保存先（app_data_dir 配下）。"""
    return app_data_dir() / ".session"


def mapping_path() -> Path:
    """mapping.json の既定パス。"""
    return session_dir() / "mapping.json"


def log_dir() -> Path:
    """ログの保存先（app_data_dir 配下）。M1 でのファイルログ用の口。"""
    return app_data_dir() / "logs"
