# MIGRATION.md — 旧プロトタイプからの移行手順

このファイルは **Phase 1〜2 でのみ使う。** 移行が完了したら削除してよい。

**このリポジトリの範囲は「検出エンジン + CLI」だけ。**
UI / デスクトップのコードは持ち込まず、旧フォルダに残す（後日 `namemask-app` へ）。

```bash
OLD=/path/to/old/namemask   # 旧フォルダ
NEW=/path/to/new/namemask   # このフォルダ
```

> **旧フォルダを消さないこと。** `frontend/` `server/` `desktop.py` はそこにしか無い。

---

## 1. 持ち込むもの

```bash
cd "$NEW"

# --- コア（無改修でそのまま） ---
mkdir -p src
cp -r "$OLD/src/namemask" src/
# UI / 配布に属するモジュールを外す
rm -rf src/namemask/server
rm -f  src/namemask/desktop.py src/namemask/devserver.py src/namemask/packaging.py

# --- テスト ---
cp -r "$OLD/tests" .
rm -f tests/test_server.py tests/test_desktop.py tests/test_packaging.py

# --- 設定・サンプルデータ ---
cp "$OLD/config.yaml" .
mkdir -p data && cp "$OLD/data/clients.sample.csv" data/

# --- 掃除 ---
find . -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null
find . -name '*.egg-info' -type d -exec rm -rf {} + 2>/dev/null
rm -rf .pytest_cache .hypothesis
```

### 残す想定のモジュール（確認用）

```
src/namemask/
  __init__.py __main__.py api.py cli.py config.py lexicon.py
  normalize.py paths.py review.py types.py
  core/       crypto.py mapping.py replacer.py restorer.py
  detectors/  address_ja.py base.py denylist.py llm_verifier.py ner.py
              ner_labels.py normalizing.py regex_ja.py structural_ja.py stub.py
  pipeline/   build.py merger.py
```

`review.py`（`--html` の単一HTML生成・依存ゼロ）は **CLI が使うので残す。**

### 依存方向の確認（P1-2）

```bash
grep -rn "server\|desktop\|devserver\|packaging" src/namemask/ tests/
```

旧リポジトリでは依存は一方向（`server` → `core`）で、`cli.py` が import するのは
`review.py` だけ。**コアの編集は不要な想定。**
想定外の参照が出たら、勝手に直さず報告して止まる。

### `config.yaml` の調整

`llm` / `session` セクションはコアが使うので残す。
`denylist.clients_csv: data/clients.csv` は**存在しないパスでも起動する**（fail-safe）
ことが README の Quickstart の前提。移行後に確認する。

---

## 2. 持ち込まないもの

### (a) UI / デスクトップ（旧フォルダに残す → 後日 `namemask-app` へ）

| 旧ファイル | 行数 | 理由 |
|---|---|---|
| `frontend/` 一式 | 1,189行 | React レビューUI。npm CI・Node追従の保守を初版で背負わない |
| `src/namemask/server/` | 262行 | FastAPI ラッパー。UI のために作られたもの |
| `src/namemask/desktop.py` | 221行 | pywebview 起動シーケンス |
| `src/namemask/devserver.py` | 41行 | 開発用サーバー起動 |
| `src/namemask/packaging.py` | 113行 | PyInstaller 用の同梱データ収集・機密混入検査 |
| `namemask.spec` | — | PyInstaller spec |
| `scripts/*.ps1`, `scripts/postbuild_check.py` | — | Windows 配布ビルド専用 |
| `tests/test_server.py` `test_desktop.py` `test_packaging.py` | — | 上記のテスト |
| `docs/desktop-build.md` | — | 配布手順。`namemask-app` の README になる |

**判断の根拠**: 現状これらは `pip install namemask` した利用者から**到達経路がない**
（`namemask serve` が未実装）。レビューは依存ゼロの `--html` で満たせる。
詳細は ADR-0011（Phase 2-4 で作成）。

### (b) 捨てるもの

| 旧ファイル | 理由 |
|---|---|
| `Plan.md` (339行) | Planv2 に置き換わった旧世代。両方生きているのが迷走の原因 |
| `Planv2.md` (338行) | 内容を `docs/` へ移してから捨てる。版番号付き文書を持ち込まない |
| `Planv3.md` (426行) | 同上。UI/配布に関する大半は `namemask-app` 側へ |
| `benchmarks/*.log` | 手動更新の数値は必ず古くなる。Phase 4 で CI 生成に置き換える |
| `release-hashes.txt` | 社内配布時の成果物ハッシュ。GitHub Releases が代替する |
| `.claude/settings.local.json` | `CLAUDE.md` が新しい真実の源 |
| `requirements.txt` / `requirements-dev.txt` | `pyproject.toml` の extras に一本化。両方あると乖離する |

> `requirements*.txt` を捨てる際、記載されていたバージョン制約が
> `pyproject.toml` の extras に漏れなく反映されているか確認する。

### (c) 絶対に持ち込まないもの（機密）

- `data/clients.csv` / `data/persons.csv` — 取引先マスタ
- `.session/` / `*.mapping.json` — 生の mapping
- `*.zip`

---

## 3. 旧プラン文書 → 新 docs の対応表

Phase 2 の作業指針。旧文書は**新リポジトリに置かず、旧フォルダを開いて参照しながら**書き移す。

| 旧 | 新 | 備考 |
|---|---|---|
| Planv2 §0 一言で | `README.md` の1行説明 | 英語に |
| Planv2 §1 目的/スコープ | `README.md` §Why + `docs/design.md` §Scope | 「やらないこと」は README の Limitations へ |
| Planv2 §2 不変条件 | `docs/security.md` §Invariants | 既に `CLAUDE.md` §2 に転記済み |
| Planv2 §3 アーキテクチャ | `docs/design.md` §Architecture | **CLI 経路のみの図に描き直す**（UI 経路は書かない） |
| Planv2 §4 技術スタック | `docs/design.md` §Stack | 採用理由は ADR へ、表だけ残す |
| Planv2 §5.1〜5.6 検出層詳細 | `docs/design.md` §Detection layers | **ここが design.md の本体。厚く書く** |
| Planv2 §6 置換・復元 | `docs/design.md` §Replace / Restore | |
| Planv2 §7 LLM検証パス | `docs/design.md` §Optional layers | NER と並べて optional 扱いに |
| Planv2 §8 評価基盤 | `docs/accuracy.md` | golden corpus の作り方・eval の読み方 |
| Planv2 §9 セキュリティ要件 | `docs/security.md` | |
| Planv2 §10 受け入れ基準 | `docs/accuracy.md` §Acceptance criteria | CI 閾値の根拠 |
| Planv2 §11 マイルストーン | **捨てる** | 完了済み。履歴は git に残る |
| Planv2 §12 Claude Code 依頼文 | **捨てる**（`CLAUDE.md` が代替） | |
| Planv2 §13 ADR-001〜007 | `docs/adr/0001〜0007` | |
| Planv3 §5 パス解決 | `docs/design.md` §Paths and data dir | `paths.py` はコア。frozen 分岐の扱いは P3-2 |
| Planv3 §12 ADR-106 / ADR-107 | `docs/adr/0008` / `0009` | config / paths はコアの判断 |
| Planv3 §8 テスト方針 | `CONTRIBUTING.md` §Testing | フロント関連の行は落とす |
| **Planv3 のそれ以外すべて** | **`namemask-app` 側へ / このリポジトリには移さない** | §2 N1-N5, §3, §6 API, §7 UI, §9, §10 情シス, §13, ADR-101〜105 / 108〜121 |
| `docs/desktop-build.md` | `namemask-app` の README | |

---

## 4. ADR 番号の対応

このリポジトリに移すのは**コアに関する9本だけ。**
各ファイルのフロントマターに `Legacy ID` として旧番号を記録する。

| 旧 | 新 | タイトル（要約） |
|---|---|---|
| ADR-001 | 0001 | 汎用PIIフレームワーク（Presidio等）を使わず薄い自前パイプラインにする |
| ADR-002 | 0002 | 評価基盤とコアエンジンを検出器より先に作る |
| ADR-003 | 0003 | NER より先に決定的層（正規化・構造ルール・辞書）で recall の床を作る |
| ADR-004 | 0004 | スコア閾値を低くし precision を意図的に犠牲にする |
| ADR-005 | 0005 | LLM をオーケストレーターにしない（追加専用の検証者に限定） |
| ADR-006 | 0006 | flashtext ではなく pyahocorasick |
| ADR-007 | 0007 | 辞書照合は fold 済み第2影テキスト上で行う |
| ADR-106 | 0008 | パス既定値は import 時定数でなく呼び出し時に遅延解決する |
| ADR-107 | 0009 | config 雛形の書き出しは load_config() の副作用にせず明示関数にする |
| — | 0010 | **新規**: ライセンスに MIT を採用する |
| — | 0011 | **新規**: OSS リポジトリの範囲をコア＋CLIに限定し、UI・配布を別リポジトリに分離する |

### `namemask-app` に持っていく ADR（このリポジトリには置かない）

ADR-101（pywebview）/ 102（onedir）/ 103（session方式）/ 104（NER非同梱）/
105（clients.csv非同梱）/ 108（per-span items）/ 109（Host/Origin/token）/
110（remask）/ 111（422汎用化）/ 112（TTL）/ 113（reducer）/ 114（revision）/
115（vitest）/ 116（起動シーケンス）/ 117（token痕跡）/ 118（wipe順序）/
119（PyInstaller同梱）/ 120（ファイルログ）/ 121（exe名）

**旧 Planv3 §12 のテキストを消さないこと。** `namemask-app` を立てるまで
旧フォルダが唯一の保管場所になる。

---

## 5. 移行後の検証

```bash
make install
make test          # 全緑（NER/LLM 要は skip でよい）
make eval          # recall/precision が旧リポジトリと一致すること
```

**旧リポジトリの数値と一致しなければ移行漏れ。** 特に確認:

- golden corpus が 99ケースあるか
  ```bash
  python -c "import json;print(len(json.load(open('tests/golden/corpus.json'))))"
  ```
- `config.yaml` の `denylist.clients_csv` が読めないパスでも起動すること（fail-safe）
- **`namemask mask` が辞書ファイルなしで動くこと**（README の Quickstart の前提）
- `namemask mask --html report.html` が動くこと（`review.py` が残っている確認）

---

## 6. 完了したら

> **削除は Phase 2 の完了後。** Phase 2（ドキュメント再編）は §3 の
> 「旧プラン文書 → 新 docs の対応表」と §4 の「ADR 番号の対応」に全面的に依存している。
> Phase 1 が終わった時点で消すと、P2-1〜P2-4 の作業指針が失われる。

- このファイル（`MIGRATION.md`）を削除する
- `CLAUDE.md` §4 のリポジトリ地図から `MIGRATION.md` の行を消す
- `PLAN.md` の Phase 1 の全チェックボックスが埋まっていることを確認
