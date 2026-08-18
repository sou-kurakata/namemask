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
| [0003](./0003-deterministic-layers-before-ner.md) | NER より先に決定的層で recall の下限を確保する | ADR-003 |
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

これら2本はプロトタイプ期に対応する ADR が無い**新規の決定**。
OSS 化の計画段階で下した判断を、蒸し返さないために決定として固定したもの。

| # | Title | Legacy |
|---|---|---|
| [0010](./0010-adopt-mit-license.md) | ライセンスに MIT を採用する | — |
| [0011](./0011-scope-oss-repo-to-core-and-cli.md) | このリポジトリの範囲をコア＋CLIに限定し、レビューUIとデスクトップアプリを別プロジェクトに分離する | — |

---

## 別プロジェクトにある ADR

以下はプロトタイプ期に決めたもののうち `namemask-app` の担当になった分（ADR-0011）。
このリポジトリには対応する ADR を置かず、一覧だけを残す。

pywebview 採用 / PyInstaller onedir / session方式の mapping 保持 / NER非同梱ビルド /
clients.csv 非同梱 / per-span items / Host・Origin・token 検証 / remask アルゴリズム /
422 の汎用化 / セッション TTL / UI reducer / revision 一致判定 / vitest 採用 /
起動シーケンスの分離 / token の URL 痕跡除去 / 終了時の wipe 順序 / 同梱データ検査 /
凍結時のファイルログ / exe 名
