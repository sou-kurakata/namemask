# Design

> **このファイルは「現在の設計」だけを書く。**
> 経緯（「P3.5 で硬化した」「M2 レビュー反映」など）は書かない — それは
> [`adr/`](./adr/) の仕事。版番号付きの別ファイル（design-v2.md）を作らない。
>
> **TODO(P2-1): 旧 `Planv2.md` §3〜§7 と `Planv3.md` §5（paths）から内容を移す。**
> 対応表は [`../MIGRATION.md`](../MIGRATION.md) §3。
> 移し終えたらこの引用ブロックを削除する。
>
> **UI / HTTP API / デスクトップに関する記述はここに書かない**（別プロジェクトの担当）。

---

## Scope

<!-- TODO: 旧 Planv2 §1。「何をするか」「何をしないか」。
     「やらないこと」のうち利用者に関係するものは README の Limitations にも書く。 -->

## Architecture

<!-- TODO: 旧 Planv2 §3 を CLI 経路のみの図として描き直す。
     mask → （人間のレビュー）→ 外部AI → unmask の1本道が伝わる形に。 -->

```
（図）
```

## Stack

<!-- TODO: 旧 Planv2 §4 + Planv3 §4 の表。採用理由は書かず ADR へのリンクにする。 -->

| Layer | Choice | ADR |
|---|---|---|
| | | |

---

## Detection layers

**ここが本体。厚く書く。** 各層について「何を検出するか」「どう検出するか」
「なぜその設計か（ADRリンク）」「既知の限界」。

### 1. Normalization (`normalize.py`)

<!-- TODO: 旧 Planv2 §5.1。NFKC 影テキスト + charmap + 逆変換 + 辞書 fold。
     「原文座標が常に真実」という不変条件がここで担保されることを明示する。 -->

### 2. Regex (`detectors/regex_ja.py`)

<!-- TODO: 旧 Planv2 §5.2。EMAIL / PHONE / MYNUMBER。チェックディジット検証。全角対応。 -->

### 3. Structural rules (`detectors/structural_ja.py`)

<!-- TODO: 旧 Planv2 §5.3。recall の主力。法人格アンカー ORG / 敬称アンカー PERSON。
     ストップワード・左境界ガード・貪欲抑制。 -->

### 4. Dictionary (`detectors/denylist.py`)

<!-- TODO: 旧 Planv2 §5.4。バリアント展開 + Aho-Corasick + fold 影上での照合。
     min_core_len の安全弁。CSV フォーマットの仕様（README.ja.md と重複させない・こちらに正） -->

### 5. Address (`detectors/address_ja.py`)

<!-- TODO: 郵便番号 + 都道府県起点住所。トラップ（住所に見えて住所でない表記）の非検出。 -->

### 6. Span merger (`pipeline/merger.py`)

<!-- TODO: 旧 Planv2 §5.6。境界拡張 / 重複マージ / 型解決（SOURCE_PRIORITY）/
     同一表記伝播 / ORG コア名伝播 と伝播境界ガード。 -->

### Entity types

| Type | Label (ja) | Placeholder example |
|---|---|---|
| PERSON | 人名 | `[[人名_1]]` |
| ORGANIZATION | 組織 | `[[組織_1]]` |
| LOCATION | 地名 | `[[地名_1]]` |
| ADDRESS | 住所 | `[[住所_1]]` |
| EMAIL | メール | `[[メール_1]]` |
| PHONE | 電話 | `[[電話_1]]` |
| MYNUMBER | マイナンバー | `[[マイナンバー_1]]` |

<!-- TODO: SOURCE_PRIORITY の表もここに載せる（types.py が単一の真実の源） -->

---

## Replace and restore

### Replacement (`core/replacer.py`)

<!-- TODO: 旧 Planv2 §6.1。後方→前方適用の理由。同一表記=同一トークンの実装。 -->

### Restoration (`core/restorer.py`)

<!-- TODO: 旧 Planv2 §6.2。長トークン優先。プレースホルダ改変耐性（【】や空白区切り）。
     未解決トークンの扱い（捏造しない）。 -->

### Mapping lifecycle

<!-- TODO: 旧 Planv2 §6.3 + Planv3 のセッション方式（ADR-0010）。
     ライブラリ=メモリ内 / CLI=別プロセスなので保存 / server=セッション内メモリ、の3経路を整理。
     暗号化（Fernet + Scrypt）の位置づけ。 -->

---

## Optional layers (additive, off by default)

どちらも **fail-safe**: 利用不可でも決定的層の床は残る。**マスクの追加のみ**行える。

### NER (`detectors/ner.py`)

<!-- TODO: 旧 Planv2 §5.5。GiNZA / ENE ラベルマッピング / fail-safe / opt-in の理由。 -->

### LLM verifier (`detectors/llm_verifier.py`)

<!-- TODO: 旧 Planv2 §7。Ollama / チャンク化 / few-shot / 幻覚防御 /
     ループバック強制と allow_remote 安全弁。 -->

---

## Paths and data directory

<!-- TODO: 旧 Planv3 §5。paths.py が単一の真実の源。遅延解決（ADR-0013）。
     dev モードと frozen モードの差。 -->

---

## Review output (`--html`)

<!-- TODO: review.py の設計。外部依存ゼロ・自己完結HTMLである理由、
     ハイライトの描き方、検出根拠（どの層が検出したか）の表示、
     HTML エスケープ、「この出力も機密である」という注意。 -->

---

## Out of scope for this repository

ローカルレビューUI（FastAPI + React）と Windows デスクトップアプリは
**別プロジェクト `namemask-app`** にある。理由は [`adr/`](./adr/) の 0011。
このリポジトリに FastAPI / React / PyInstaller のコードを持ち込まない。

## Related documents

- [`accuracy.md`](./accuracy.md) — 評価方法と実測値
- [`security.md`](./security.md) — 脅威モデルと不変条件
- [`adr/`](./adr/) — 設計判断の理由

