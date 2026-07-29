# Security model

> **TODO(P2-2): 旧 `Planv2.md` §2 §9 から内容を移す。**
> サーバー関連の脅威（CSRF / DNS rebinding / トークン）は別プロジェクトの担当なので移さない。
> 移し終えたらこの引用ブロックを削除する。
> 脆弱性の報告手順は [`../SECURITY.md`](../SECURITY.md) にあり、ここには重複させない。

---

## What namemask protects

**「機密テキストがマシンから出ない」こと。** これが唯一の中心的な保証。

## What namemask does NOT protect

**検出漏れは脆弱性ではない。** namemask は recall 100% を主張していない
（実測 97.7% / 99ケース）。**人間がマスク結果をレビューする前提で設計されている。**
namemask は自動的な境界（gate）ではなく、レビューの補助（aid）である。

<!-- TODO: この節を厚く書く。利用者の期待値を正しく設定することが、
     このツールの安全性の一部である。 -->

---

## Invariants

これを壊す変更は受け付けない。テストで担保する。

### Core

1. **可逆。** `unmask(mask(x))` で原文が完全復元される。
2. **失敗は非対称。** 検出漏れ＝漏洩（致命）、過剰マスク＝軽微。**recall 最優先。**
3. **完全ローカル。** 外部通信ゼロ（telemetry 含む）。モデル・辞書もローカル。
4. **決定的コア。** 同じ入力→同じ出力。エージェントの推論ループで駆動しない。
5. **LLM は追加専用の検証者。** 解除・変更は不可。落ちても決定的層の床が残る。
6. **原文を書き換えない。** 正規化は影のコピー上、置換は原文座標に対して。
7. **生値を捏造しない。** 復元不能は未解決として報告する。

### Output and storage

8. **LLM エンドポイントはループバック限定**（`localhost` / `127.0.0.0/8` / `::1`）。
   非ループバック URL は既定で例外。`llm.allow_remote: true` が唯一の安全弁で、
   既定 true にしない。
9. **ログ・例外・レポートに原文断片を残さない。** NER の未マッピングラベル警告も
   ラベル名のみ。
10. **mapping は生の機密。** ライブラリAPIは既定メモリ内。CLI の保存は限定ディレクトリ・
    0o700/0o600・gitignore・stderr 警告。
11. **`--html` の出力も原文を含む。** 外部CDN・外部JSを参照しない自己完結HTMLを維持する。
12. **外部ツールの都合でコアを改修しない。**

---

## Threat model

### T1: Data egress via the tool itself

<!-- TODO: telemetry / 依存ライブラリの通信 / モデルダウンロード。
     「外部AIへの送信は人間のコピペのみ」という設計上の選択とその理由。 -->

### T2: Raw text leaking into artifacts

<!-- TODO: ログ / 例外メッセージ / 検出根拠レポート / NER の未マッピングラベル警告。
     テストフィクスチャや配布物（wheel）への実データ混入防止。CI の secrets-guard。 -->

### T3: The `--html` review page

<!-- TODO: 生成HTMLが原文を含むこと。HTML エスケープ。
     外部参照ゼロ（CDN / 外部JS / 画像）を維持する理由。 -->

### T4: Non-loopback LLM endpoint

<!-- TODO: ループバック強制の実装。allow_remote 安全弁の位置づけと、
     それを既定 true にしない理由。 -->

### T5: Mapping file compromise

<!-- TODO: パーミッション（Windows で 0o600 が no-op である既知の制約）/
     保存先の限定 / --wipe / --encrypt（Fernet + Scrypt）と改竄検知。 -->

### T6: Incorrect restoration

<!-- TODO: 復号失敗・未知トークンで「推測復元しない」設計。 -->

---

## Out of the threat model

- ローカルでコード実行権限を持つ攻撃者（同一ユーザー）
- 第三者モデル（GiNZA / Ollama モデル）自体の脆弱性
- ホスト型サービスとしての運用（そもそも設計に含まない。不変条件3違反）
- **ローカルHTTPサーバーとデスクトップアプリ** — このパッケージに含まれない
  （[`adr/`](./adr/) の 0011）。別プロジェクトの担当。

---

## Reporting

[`../SECURITY.md`](../SECURITY.md) を参照。
