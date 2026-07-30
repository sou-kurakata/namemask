# Architecture Decision Records

なぜ namemask がこの形になっているかの記録。
**新しい設計判断は、実装の前に ADR を書く**（[../../CONTRIBUTING.md](../../CONTRIBUTING.md)）。

書き方: [`template.md`](./template.md) をコピーし、次の連番を取る。
Context / Options considered / Decision / Consequences の4節。
**採用しなかった選択肢とその理由を必ず残す。**

`Legacy ID` は旧プロトタイプのプラン文書での番号。コード中のコメントや docstring に
残っている `ADR-001` `ADR-106` 等の参照はこの列で引く。

---

## Detection and core engine

| # | Title | Legacy |
|---|---|---|
| [0001](./0001-thin-in-house-pipeline-over-generic-pii-framework.md) | 汎用PIIフレームワーク（Presidio等）を使わず薄い自前パイプラインにする | ADR-001 |
| [0002](./0002-build-eval-harness-and-core-before-detectors.md) | 評価基盤とコアエンジンを検出器より先に作る | ADR-002 |
| [0003](./0003-deterministic-layers-before-ner.md) | NER より先に決定的層で recall の床を作る | ADR-003 |
| [0004](./0004-favor-recall-over-precision.md) | スコア閾値を低くし precision を意図的に犠牲にする | ADR-004 |
| [0005](./0005-llm-as-additive-verifier-not-orchestrator.md) | LLM をオーケストレーターにしない（追加専用の検証者に限定） | ADR-005 |
| [0006](./0006-pyahocorasick-over-flashtext.md) | flashtext ではなく pyahocorasick を使う | ADR-006 |
| [0007](./0007-dictionary-matching-on-folded-second-shadow.md) | 辞書照合は fold 済み第2影テキスト上で行う | ADR-007 |

## Paths and configuration

| # | Title | Legacy |
|---|---|---|
| [0008](./0008-resolve-default-paths-lazily.md) | パス既定値は import 時定数でなく呼び出し時に遅延解決する | ADR-106 |
| [0009](./0009-config-scaffolding-as-explicit-function.md) | config 雛形の書き出しは load_config() の副作用にせず明示関数にする | ADR-107 |

## Open source release

**TODO(P2-4): この2つは新規に書く。** PLAN.md の判断を決定として固定するため。

| # | Title |
|---|---|
| 0010 | ライセンスに MIT を採用する _(未作成)_ |
| 0011 | このリポジトリの範囲をコア＋CLIに限定し、レビューUIとデスクトップアプリを別プロジェクトに分離する _(未作成)_ |

**ADR-0011 に必ず書くこと**（後で蒸し返さないため）:

- 却下した選択肢: 同居 / server だけ同居 / リポジトリ完全分割
- 決定の根拠: 現状 CLI 利用者から到達経路がない（`namemask serve` 未実装）/
  npm CI・Node追従の保守を初版で背負わない / レビューは依存ゼロの `--html` で満たせる /
  リポジトリ境界が「UI の都合でコアを改修しない」を物理的に強制する
- **見直し条件**: `namemask serve` の需要が issue で確認できたら v0.2.0 で再統合を検討する
- 受け入れたトレードオフ: `remask`（誤検出の解除・手動追加）が OSS 側に無い。
  server/UI/desktop の ADR 19本が OSS の資産にならない

---

## 別プロジェクトにある ADR

旧 `Planv3.md` §12 の以下は `namemask-app` の担当。参照が必要なら旧フォルダを見る。

pywebview 採用 / PyInstaller onedir / session方式の mapping 保持 / NER非同梱ビルド /
clients.csv 非同梱 / per-span items / Host・Origin・token 検証 / remask アルゴリズム /
422 の汎用化 / セッション TTL / UI reducer / revision 一致判定 / vitest 採用 /
起動シーケンスの分離 / token の URL 痕跡除去 / 終了時の wipe 順序 / 同梱データ検査 /
凍結時のファイルログ / exe 名
