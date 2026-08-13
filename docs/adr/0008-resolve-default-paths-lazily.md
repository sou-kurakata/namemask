# ADR-0008: パス既定値は import 時定数でなく呼び出し時に遅延解決する

- **Status**: Accepted
- **Date**: 2026-07-30 <!-- 旧 Planv3.md §12 からの移設日。原決定はプロトタイプ期（日付未記録） -->
- **Legacy ID**: ADR-106

## Context

config.yaml / mapping.json / ログの既定パスをどこで決めるか。当初は
`config.py` の `_DEFAULT_PATH`、`mapping.py` の `_DEFAULT_FILE` のように
**モジュール import 時に評価される定数**として持っていた。

これが成立しない条件が2つある:

1. **凍結ビルド（PyInstaller）** —— `__file__` は `sys._MEIPASS` 配下の
   読み取り専用の一時展開先になり、書き込みにも編集にも使えない。
   `sys.frozen` の判定は**実行時**にしか分からない。
2. **cwd が不定** —— スタートメニューやショートカットから起動すると
   カレントディレクトリが `C:\Windows\System32` になりうる。
   そこに mapping（生の機密。不変条件10）を書けばそれ自体が事故になる。

さらに import 時定数はテストからも扱いにくい。`monkeypatch` で環境変数や
`sys.frozen` を差し替えても、定数はすでに評価済みで動かない。

## Options considered

### (A) 従来どおり `config.py` / `mapping.py` の import 時定数として持つ

- 利点: 変更不要。参照が単純。
- 欠点: 凍結モードで誤ったベース（`sys._MEIPASS` や cwd）に貼り付く。
  テストの monkeypatch が効かない。パス解決の知識が複数モジュールに散る。

### (B) 既定パスを `paths.py` の関数（`app_data_dir()` など）に集約し、
呼び出し時に解決する

- 利点: 凍結判定と環境変数を実行時に反映できる。テストから差し替えられる。
  パス解決の真実の源が1か所になる。
- 欠点: 「定数を読む」より1段間接になる。呼び出しごとに解決コストがかかる
  （実際には無視できる）。

## Decision

**(B) を採用する。**

(A) を却下した理由は、決定に必要な情報（凍結かどうか、`LOCALAPPDATA` が何か）が
import 時にはまだ確定していないこと。定数化は「早すぎる確定」であり、
凍結モードでは確実に誤る。

`paths.py` を**単一の真実の源**とし、config / mapping / CLI / ログはすべて
そこを経由する。

補足として2つの例外・制約を置く:

- **開発モードの config.yaml だけは `__file__` 起点**（リポジトリ同梱）を維持する。
  「どの cwd から呼んでも同梱 config を読む」という既存の挙動を保つため。
  凍結モードでは編集可能にすることが目的なので `app_data_dir()` 配下へ移す。
  mapping とログの開発モード側は従来どおり cwd 相対。
- **パス解決関数は副作用を持たない純関数**とする（`app_data_dir` / `config_path` /
  `session_dir` / `mapping_path` / `log_dir`）。ディレクトリ作成は書き込み時
  （`MappingStore.save` / `ensure_config_file`）に限る。パスを問い合わせただけで
  ディレクトリができるのは、テストと呼び出し側にとって予測不能な挙動になる。

## Consequences

- `src/namemask/paths.py` が全パス解決の入口。`config.py` は
  `paths.config_path()`、`core/mapping.py` は `paths.mapping_path()`、
  `cli.py` は `paths.mapping_path()` を呼び出し時に引く。
- テストは `sys.frozen` と `LOCALAPPDATA` を monkeypatch して両モードを検証できる
  （`tests/test_paths.py`）。
- 純関数であることの帰結として、`app_data_dir()` を呼んでもディレクトリはできない。
  書き込み側が `mkdir(parents=True, exist_ok=True)` を持つ責務を負う。
- `LOCALAPPDATA` が無い異常時はユーザーホーム配下へフォールバックする。
  いずれにせよ cwd / System32 には書かない、というのがこの分岐の要点。

---

## Follow-up: `sys.frozen` 分岐を残すか（2026-08-13 決定）

上の「見直し条件」に対する結論。**分岐はこのリポジトリに残す。**

PyInstaller で凍結ビルドを作るのは別リポジトリ `namemask-app` 側であり（ADR-0011）、
このリポジトリの利用者（`pip install namemask`）が `sys.frozen` に入ることはない。
「使わないコードは消す」の原則からは (B) 外す が自然に見えるが、却下した。

- **通常実行の挙動に影響しない。** `is_frozen()` は常に `False` を返し、分岐は
  評価されない死んだ枝になる。残すコストは `paths.py` の十数行だけで、
  `tests/test_paths.py` が両モードを monkeypatch で検証し続ける。
- **外すと不変条件12を破る圧力になる。** `namemask-app` は PyPI 経由で同じ
  `paths.py` を使う。分岐を外せば、アプリ側は `paths.py` をフォークするか、
  「配布の都合でコアに分岐を戻してほしい」と要求することになる。後者は
  **外部ツールの都合でコアを改修する**ことそのもので、リポジトリを分けた意味を消す。
- **CLI 利用者にとって何が良くなるかを説明できない。** 削除の利点は
  「行数が減る」だけで、`pip install namemask` の体験は1ミリも変わらない。

**この分岐に新しい機能を足さない。** PyInstaller 固有の要求（同梱データの解決、
起動シーケンス、ログの置き場）は `namemask-app` 側の issue であり、
`paths.py` に持ち込まない。凍結時の書き込み先を「cwd / System32 ではない場所」に
固定する、という現在の役割だけを維持する。

- **見直し条件**: `namemask-app` が `paths.py` を使わなくなったとき
  （独自のパス解決を持つ、あるいはプロジェクトが終了したとき）は、分岐を外してよい。
