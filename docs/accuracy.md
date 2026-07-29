# Accuracy

> **TODO(P2-1 / P4-3): 旧 `Planv2.md` §8（評価基盤）§10（受け入れ基準）から内容を移す。**
> 数値ブロックは Phase 4-3 で `make eval` の出力から生成するようにし、
> **手で更新しない。** 移行が終わったらこの引用ブロックを削除する。

---

## Golden corpus

`tests/golden/corpus.json` — **91ケース、すべて架空名。**

<!-- TODO: ケースの構造（原文 / 正解スパン / nth によるオカレンス指定）、
     _build_corpus.py による surface 検証、ケースの選び方の方針を書く。 -->

**新しいケースを追加するときのルール**は
[`../CONTRIBUTING.md`](../CONTRIBUTING.md) を参照。**架空名のみ。**

## Evaluation method

<!-- TODO: 旧 Planv2 §8.2。partial 一致の定義、型別集計、真のアブレーション
     （層を1つ外して実測する）、見逃し明細の出力。 -->

```bash
make eval                        # 決定的層 + 住所層
python tests/eval.py --ner       # NER 有効（要 ja_ginza・CI では走らない）
```

## Property-based tests

<!-- TODO: 旧 Planv2 §8.3。hypothesis による round-trip プロパティ。
     「何を証明しているのか」を書く。 -->

---

## Acceptance criteria (CI thresholds)

CI がこの閾値を検査する。**下回るとビルドが落ちる。**

| Metric | Threshold |
|---|---|
| 辞書登録済み取引先の recall（全バリアント表記込み） | 100% |
| 正規表現対象（EMAIL / PHONE / MYNUMBER・全角含む） | 100% |
| 法人格を含む組織名の recall | ≥ 98% |
| 全体 recall（partial 基準・NER/LLM off） | ≥ 95% |
| 全体 precision | ≥ 70%（recall 優先のトレードオフを許容） |
| round-trip 完全一致 | 100% |
| 同一表記の文書内一貫性 | 100% |

---

## Measured results

> **この節は `make eval` の出力から生成する。手で編集しない。**
> TODO(P4-3): 生成の仕組みを作るまでは空欄にしておく。
> 古い数値を置くより、無い方がよい。

<!-- BEGIN GENERATED -->
<!-- END GENERATED -->

## Known false negatives

<!-- TODO: 残存する検出漏れの傾向を正直に書く。
     「未知の固有名詞」「ひらがな・カタカナ表記の姓」「署名ブロック」など。
     どの optional 層がそれを補完しうるかも書く。
     これを隠すと信頼を失う。README の Limitations と整合させる。 -->
