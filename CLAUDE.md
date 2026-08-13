# CLAUDE.md

このリポジトリで作業するときの指示書。**セッション開始時に必ず読む。**
実行計画は [`PLAN.md`](./PLAN.md)。

---

## 1. このプロジェクトは何か

**namemask** — 日本語の機密テキスト（取引先名・担当者名・連絡先・住所）を、
外部AIに投げる**前**にローカルで仮名化し、外部AIの応答を**元の固有名詞に復元**する
完全ローカルの Python ツール。

- 中核は**決定的（deterministic）な検出パイプライン**: 正規化 → 正規表現 → 構造ルール →
  辞書(Aho-Corasick) → 住所 → スパン統合 → 置換。
- NER（GiNZA）と LLM検証（Ollama）は**追加専用・既定 off の optional 層**。
- 実測: golden corpus 99ケースで **precision 1.00 / recall 97.7%**（決定的層＋住所層）。
- レビューは `--html` が出力する**依存ゼロの単一HTML**（`review.py`）で行う。

**このリポジトリの範囲は「検出エンジン + CLI」だけ。**
ローカルレビューUI（FastAPI + React）と Windows デスクトップアプリは
**別リポジトリ `namemask-app`**（private）にあり、`namemask` を PyPI 経由で依存する。
このリポジトリに FastAPI / React / PyInstaller のコードを持ち込まない（ADR-0011）。

**現在のフェーズ: OSS化（v0.1.0 を PyPI に出す）。検出器の精度改善は凍結中。**

---

## 2. 絶対に崩さない不変条件

これを壊す変更は、理由が何であれ**行わずに代替案を提示して確認を求める**。

### コアの不変条件

1. **双方向・可逆。** 同じ固有名詞は常に同じプレースホルダ。`unmask(mask(x))` で原文が完全復元される。
2. **失敗は非対称。** 検出漏れ＝情報漏洩（致命）、過剰マスク＝軽微。**recall 最優先。**
   誤検出は人間レビューで捨てられるが、見逃しは捨てられない。
3. **完全ローカル。** 外部通信ゼロ。telemetry を出さない。モデルも辞書もローカル。
4. **決定的コア。** 検出→統合→置換→レビュー→復元は固定経路の決定的コード。
   同じ入力→同じ出力。エージェントの推論ループで駆動しない。
5. **LLM は追加専用の検証者。** マスクの「追加」のみ許可、「解除・変更」は絶対不可。
   LLM が落ちても決定的マスクの床が残る（fail-safe）。
6. **原文は書き換えない。** 検出のための正規化は影のコピー上で行い、置換は常に原文座標に対して行う。
7. **生値を捏造しない。** 復元できない値を推測で埋めない。復号失敗・未知トークンは
   エラーか未解決として報告する。

### 出力と保存の不変条件

8. **生テキストはマシンから出ない。** LLM エンドポイントはループバック限定
   （`localhost` / `127.0.0.0/8` / `::1`）。非ループバック URL は既定で例外にする。
   `llm.allow_remote: true` が唯一の安全弁で、これを既定 true にしない。
9. **ログ・例外・レポートに原文断片を残さない。** NER の未マッピングラベル警告も
   ラベル名のみ。検出根拠レポートは人間レビュー用に端末へ出すだけ。
10. **mapping は生の機密。** ライブラリAPIは既定メモリ内。CLI は別プロセスのため保存するが、
    保存先は限定・dir 0o700 / file 0o600・gitignore 済み・保存時に stderr 警告・`--wipe` を案内。
11. **`--html` のレビュー出力も原文（＝機密）を含む。** 外部CDN・外部JSを参照しない
    自己完結HTMLであることを維持する。
12. **外部ツールの都合でコアを改修しない。** UI や配布側（`namemask-app`）の要求で
    `src/namemask/` に手を入れたくなったら、それは設計の誤り。ADR を書いて立ち止まる。

---

## 3. OSS化フェーズの方針（迷ったらここに戻る）

- **D1: このリポジトリは「検出エンジン + CLI」だけ。** 成果物は
  `pip install namemask` → `namemask mask`。ローカルUIとデスクトップアプリは
  **別リポジトリ `namemask-app`** に分離し、PyPI 経由で `namemask` に依存させる（ADR-0011）。
- **D2: OSS化を先にやる。** 社内パイロットは v0.1.0 の成果物を使う。
  パイロット由来の要望で OSS 側のコア設計を曲げない。
- **D3: 文書は英語主・日本語併記。** `README.md`（英語）+ `README.ja.md`（日本語・詳細）。

### 判断に迷ったときの1問

> **「これは『検出エンジン + CLI』の要求か、『アプリ（UI・配布）』の要求か？」**

アプリ側の要求なら、このリポジトリでは何もしない。`namemask-app` の issue にする。
コアに必要な変更なら、**まず「CLI 利用者にとって何が良くなるか」を説明できること**を確認する。
説明できないなら、それはアプリ側の要求である。

### このフェーズでやらないこと

「今はやらない」ではなく「**v0.1.0 の判断軸に入れない**」。提案もしない。

- NER / LLM 層の精度改善（extras として現状維持。改善は v0.2.0 以降の議題）
- **FastAPI サーバー / React UI / PyInstaller 関連のコード**（`namemask-app` の担当）
- `namemask serve` サブコマンド（v0.2.0 の議題。ADR-0011 の「見直し条件」を参照）
- ホスト型Webサービス化（不変条件 3・8 違反）
- 日本語以外の言語のPII対応
- 検出器の新規追加

---

## 4. リポジトリの地図

```
namemask/
├── CLAUDE.md               この文書
├── PLAN.md                 OSS化の実行計画（作業はここから取る）
├── README.md               英語・利用者向け
├── README.ja.md            日本語・詳細
├── src/namemask/           ★ 主役
│   ├── core/               replacer / restorer / mapping / crypto
│   ├── detectors/          regex_ja / structural_ja / denylist / address_ja / ner / llm_verifier
│   ├── pipeline/           merger / build
│   ├── api.py cli.py       公開インターフェース
│   ├── review.py           --html の単一HTML生成（依存ゼロ）
│   └── paths.py config.py normalize.py lexicon.py types.py
├── tests/                  ★ 最大の資産。golden/corpus.json + eval.py
├── docs/
│   ├── design.md           現在の設計（1本）
│   ├── accuracy.md         golden corpus と実測値（eval 出力から生成）
│   ├── security.md         脅威モデルと不変条件
│   └── adr/                設計判断ログ（1ファイル1決定）
└── data/clients.sample.csv 辞書の雛形（架空データのみ）
```

**このリポジトリに存在しないもの**（`namemask-app` にある）:
`frontend/` `src/namemask/server/` `desktop.py` `devserver.py` `packaging.py`
`namemask.spec` `scripts/*.ps1`、および対応する
`tests/test_server.py` `test_desktop.py` `test_packaging.py`。

---

## 5. 開発コマンド

```bash
make install      # 開発依存を入れる（editable install + dev extra）
make test         # pytest（NER/LLM 要は skip）
make test-all     # pytest 全実行（GiNZA / Ollama をローカルに要求）
make eval         # tests/eval.py（決定的層の実測 + アブレーション）
make lint         # ruff check + ruff format --check
```

- **CI の必須ゲート**: ubuntu × py3.10/3.11/3.12 ＋ windows/macos × py3.12 のテスト、
  lint、eval 閾値、機密混入チェック、`pip install` からの round-trip スモーク。
- **Windows も必須にしている。** 主要な利用者が Windows で、旧プロトタイプは
  Windows 前提で書かれていた。パス・エンコーディングの退行をここで捕まえる。
- NER / LLM を要するテストは CI では skip（モデル同梱不可）。ローカルで `make test-all`。

---

## 6. 受け入れ基準（数値。CI の閾値ゲート）

| 指標 | 基準 |
|---|---|
| 辞書登録済み取引先の recall（全バリアント表記込み） | **100%** |
| 正規表現対象（EMAIL / PHONE / MYNUMBER、全角含む） | **100%** |
| 法人格を含む組織名の recall | **≥ 98%** |
| 全体 recall（partial 基準・NER/LLM off） | **≥ 95%** |
| 全体 precision | ≥ 70%（recall優先のトレードオフを許容。実測は 1.00） |
| round-trip 完全一致 | **100%**（golden 全ケース + hypothesis） |
| 同一表記の文書内一貫性 | **100%** |

**この数字を下げる変更は入れない。** eval の数値が動く変更は PR に before/after を書く。

---

## 7. 変更するときのルール

1. **受け入れ基準テストを先に書く。** TDD を維持する（既存方針の継承）。
2. **新しい設計判断が発生したら ADR を書いてから実装する。**
   `docs/adr/template.md` をコピーし、連番で追加。Context / Decision / Consequences の3節。
   採用しなかった選択肢とその理由を必ず残す。
3. **設計文書は追記ではなく置換する。**
   `docs/design.md` は常に「**現在の**設計」だけを書く。
   「P3.5で〜した」「M2レビュー反映」のような経緯は書かない（それは ADR の仕事）。
   **`Plan.md` `Planv2.md` `Planv3.md` のような版番号付き文書を新規作成しない。**
   design.md を書き換えたくなったら、書き換える。新しい版を作らない。
4. **1ステップ完了ごとに停止し、差分の要約を報告して次の指示を待つ。**
   PLAN.md の1タスク = 1コミット = 1報告。まとめて進めない。
5. **セキュリティ判断（bind先・トークン・ヘッダ検証・ループバック強制）を弱めない。**

---

## 8. 機密データの取り扱い（最重要）

このツールの利用者は機密テキストを扱う。リポジトリに機密を混入させたら信頼はゼロになる。

- **実在の人名・企業名・住所・電話番号・メールアドレスを一切コミットしない。**
  テスト・ドキュメント・コメント・コミットメッセージすべてで。**架空名のみ。**
- `data/clients.csv` / `data/persons.csv` は gitignore 済み。追跡するのは
  `data/clients.sample.csv`（架空データ）のみ。
- `.session/` と `*.mapping.json` は gitignore 済み。**生の mapping は絶対にコミットしない。**
- ログ・例外メッセージ・API レスポンスに原文断片を載せない。
  Pydantic の 422 は入力値をエコーするので汎用文言に差し替える（既存実装）。
- 新しいテストケースを golden corpus に追加するときは、架空名であることを目視確認する。
- コミット前に確認: `git diff --staged` で機密らしい文字列がないか見る。

---

## 9. 現在の作業

**次にやることは常に [`PLAN.md`](./PLAN.md) の未チェック先頭タスク。**
勝手に先のタスクへ進まない。PLAN.md に無い作業を思いついたら、実装せずに提案する。
