# Accuracy

このツールの精度は**測定されたものだけを書く。** 下の「Measured results」は
`make eval` が実測から生成し、CI が「コミット済みの数値が実測と一致すること」を
検査する。手で書き換えた数値は CI で落ちる。

---

## Golden corpus

`tests/golden/corpus.json` — **99ケース、すべて架空名。**

1ケースは「原文」と「その中の正解エンティティ」の組で、次の形をしている。

```json
{
  "id": "org_pre_01",
  "category": "org-prefix",
  "text": "株式会社アオヤマ商事の件でご連絡いたしました。",
  "entities": [{ "surface": "株式会社アオヤマ商事", "type": "ORGANIZATION" }],
  "note": ""
}
```

- **正解は座標ではなく表層（`surface`）で書く。** 文字位置を手で数えると必ずずれる。
  評価時に `GoldenStubDetector` が本文を走査して**全出現**をスパンに解決する。
  「同じ表記は文書内で常に同じ扱い」という不変条件と、同じ規則で解決している。
- **`nth` は「その出現だけが正解」を表す。** 複合語トラップ用。例えば
  `"青葉様より、青葉区役所への申請書を確認しました。"` は `nth: 0` を付けて、
  1つ目の `青葉`（人名）だけが正解＝2つ目（`青葉区役所` の内部）へ伝播したら
  **誤検出**であることを表現する。
- **`category` が評価の切り口。** 受け入れ基準の一部は分類ごとに測る
  （法人格を含む組織名、辞書登録済み取引先、誤検出トラップなど）。
  分類は `tests/eval.py` の `LEGAL_FORM_CATEGORIES` / `DICTIONARY_CATEGORIES` が参照する。

コーパスは `tests/golden/_build_corpus.py` から生成する。生成時に
**`surface` が `text` の部分文字列であること**・`id` が重複しないこと・
`type` が既知の型であること・`nth` が実際の出現数の範囲内であることを検査するので、
「本文に存在しない正解」が混入しない。

**新しいケースを追加するときのルール**は
[`../CONTRIBUTING.md`](../CONTRIBUTING.md) を参照。**架空名のみ。**

## Evaluation method

```bash
make eval                        # 決定的層 + 住所層（= python tests/eval.py --address --write-docs）
python tests/eval.py --ner       # NER 有効（要 ja_ginza・CI では走らない）
```

- **照合は型一致が必須。** 位置が合っていても型が違えば当たりにしない。
- **recall は partial（重なり）基準。** 正解スパンに1文字でも重なる同型の検出があれば
  「拾えた」と数える。マスクの目的は情報を残さないことなので、境界が1文字ずれても
  漏洩は起きない——ここを exact にすると、実害のない境界差で recall が下がり、
  **本当の見逃しが数字に埋もれる。** exact 一致は `exact_recall` として別に出す。
- **precision も同じ基準**（各検出スパンが同型の正解と重なるか）で測る。
  誤検出は人間のレビューで捨てられるが見逃しは捨てられない、という非対称を
  数字の上でも保つ（[ADR-0004](./adr/0004-favor-recall-over-precision.md)）。
- **層別寄与は「真のアブレーション」で測る。** 検出結果の `sources` を後から
  フィルタする方法は正しくない——統合層が付ける `boundary` / `propagation` は
  他層由来のスパンから生まれるため、寄与が二重に数えられる。代わりに
  **層を1つ無効にしたパイプラインを組み直して再評価**し、full との差を寄与とする。
- **見逃し・誤検出は明細で出す。** 集計値だけでは何が起きているか分からない。
  下の GENERATED ブロックに全件（ケースID / 型 / 表層）が載る。

## Property-based tests

`tests/test_roundtrip.py` が hypothesis で、ランダムな日本語混じりテキストと
ランダムな検出スパンを生成して次の性質を検査する（各400例）。

- **round-trip**: `unmask(mask(x)) == x`。座標処理のオフバイワンや置換順序のバグは、
  golden の99ケースより無作為な入力の方がよく炙り出す。
- **残存ゼロ**: マスク後のテキストに、マスク対象の表層が1つも残らない。
  「1箇所だけ置換し損ねる」種類のバグは、これが無いと round-trip では見つからない
  （復元すれば元に戻るため）。
- **非重複**: スタブが返すスパンが重ならない。置換エンジンは非重複を前提にしており、
  前提が崩れたことを置換側の例外ではなくこちらで先に検出する。

golden 側の round-trip（99ケース全件・プレースホルダ改変込み）は
`tests/test_golden.py` が担当する。

---

## Acceptance criteria (CI thresholds)

CI がこの閾値を検査する。**下回るとビルドが落ちる。**
数値の出どころは [`../CLAUDE.md`](../CLAUDE.md) §6、実装は `tests/eval.py` の定数
（`MIN_OVERALL_RECALL` など）で、テストも CI も**同じ定数**を参照する。

| Metric | Threshold | どこが検査するか |
|---|---|---|
| 辞書登録済み取引先の recall（全バリアント表記込み） | 100% | `eval --assert-thresholds` / `test_pipeline_p3.py` |
| 正規表現対象（EMAIL / PHONE / MYNUMBER・全角含む） | 100% | 同上 |
| 法人格を含む組織名の recall | ≥ 98% | 同上 |
| 全体 recall（partial 基準・NER/LLM off） | ≥ 95% | `eval --assert-thresholds` |
| 全体 precision | ≥ 70%（recall 優先のトレードオフを許容） | 同上 |
| round-trip 完全一致 | 100% | `test_golden.py` / `test_roundtrip.py` |
| 同一表記の文書内一貫性 | 100% | `test_golden.py` |

round-trip と一貫性を eval で測らないのは、これらが**スパン集合ではなく
置換・復元の性質**だから。検出が全滅しても「何も検出しなかった原文」は
そのまま復元できてしまうので、eval の指標としては意味を持たない。

---

## Measured results

<!-- BEGIN GENERATED -->

> この節は `make eval` が生成する。**手で編集しない**（編集しても CI の `--check-docs` が差分を検出して落ちる）。

構成: 決定的層 + 住所層（NER off / LLM off）・`python tests/eval.py --address`

- ケース数: **99** / 正解スパン: **269** / 検出スパン: **263**

| Metric | Result |
|---|---|
| Recall (partial) | **0.9777** |
| Recall (exact) | **0.9777** |
| Precision | **1.0000** |
| F1 | **0.9887** |

### Per-type recall

| Type | Recall | Hits / Gold |
|---|---|---|
| PERSON | 0.9506 | 77 / 81 |
| ORGANIZATION | 0.9808 | 102 / 104 |
| ADDRESS | 1.0000 | 5 / 5 |
| EMAIL | 1.0000 | 36 / 36 |
| PHONE | 1.0000 | 40 / 40 |
| MYNUMBER | 1.0000 | 3 / 3 |

### Layer contribution (true ablation)

層を1つ無効にしたパイプラインで再評価し、full との recall 差を寄与とする。

| Layer | Recall drop if removed |
|---|---|
| structural | −0.3643 |
| regex | −0.2937 |
| denylist | −0.0483 |
| address | −0.0186 |

### False negatives

残る見逃しは **6件**。

| Case | Type | Surface |
|---|---|---|
| `sig_01` | PERSON | 山田太郎 |
| `sig_02` | PERSON | 田中花子 |
| `sig_03` | PERSON | 佐藤健 |
| `sig_04` | PERSON | 鈴木一郎 |
| `unknown_org_01` | ORGANIZATION | オリオン企画 |
| `unknown_org_02` | ORGANIZATION | ネビュラ物流 |

### False positives

誤検出ゼロ（precision 1.00）。

<!-- END GENERATED -->

## Known false negatives

**隠さない。** 見逃しは情報漏洩であり、それを知らずに使われる方が有害である。
上の明細（GENERATED）に全件が出ているが、傾向としては**2つしかない。**

### 1. 敬称の付かない署名ブロックの人名（4件）

```
営業部 山田太郎
TEL: 03-1234-5678
```

構造ルール層は敬称（`様` `さん` `部長` …）をアンカーに人名を取るので、
アンカーの無い署名行の氏名は取れない。**同じ行の電話番号やメールは regex 層が
確実に取る**ため、署名ブロックが丸ごと素通りするわけではない。

補完する手段は2つ。**辞書に登録する**（自社の担当者名は有限で、`persons_csv` に
書けば 100% 落ちる）か、**NER 層を有効にする**（`pip install namemask[ner]`。
GiNZA が固有表現として拾う）。

### 2. 法人格を持たず辞書にも無い会社名（2件）

`オリオン企画` `ネビュラ物流` のような、`株式会社` 等を伴わない表記。
法人格アンカーも辞書も効かないため、決定的層では原理的に取れない。
これも**辞書に登録すれば 100%**（取引先は有限）、あるいは NER 層で補う。

### この2つが意味すること

決定的層で取れるのは「**表層に手がかりがあるもの**」だけで、それは設計どおりである
（[ADR-0003](./adr/0003-deterministic-layers-before-ner.md)）。
未知の固有名詞を取りこぼす前提で、**送信前に人間がレビューする**運用と、
**自分の取引先・担当者を辞書に入れる**運用が併せて必要になる。
README の Limitations もこの前提で書かれている。
