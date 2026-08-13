## 何を変えたか / What changed

<!-- 1〜3行。なぜ必要かも含める -->

## 種類 / Type

- [ ] fix（バグ修正）
- [ ] feat（機能追加）
- [ ] docs
- [ ] refactor / chore / test
- [ ] **detector change（検出器の変更）** ← 該当する場合は下の節を必ず埋める

---

## 検出器を変更した場合 / If you changed a detector

`make eval` の出力を before / after で貼る。

| Metric | Before | After |
|---|---|---|
| Overall recall (partial) | | |
| Precision | | |
| PERSON recall | | |
| ORGANIZATION recall | | |
| 層別寄与の変化（アブレーション） | | |

<details><summary>eval output (after)</summary>

```
（ここに貼る）
```

</details>

- [ ] golden corpus にケースを追加した（`_build_corpus.py` を編集して再生成・**架空名のみ**）
- [ ] ケースを先に追加し、失敗するのを確認してから実装した
- [ ] `make eval` が書き換えた `docs/accuracy.md` の差分をコミットに含めた
      （**CI が実測との一致を検査する**）
- [ ] recall が下がる変更の場合、その理由を上に書いた（**閾値の変更は別 PR**）

---

## チェックリスト / Checklist

- [ ] **実在の人名・企業名・住所・電話番号・メールアドレスを含んでいない**
      （コード・テスト・docs・コミットメッセージすべて）
- [ ] `make test` が緑
- [ ] `make lint` が緑
- [ ] 不変条件（CONTRIBUTING.md の10項目）を壊していない
- [ ] 新しい設計判断があれば ADR を追加した（`docs/adr/`）
- [ ] 挙動が変わる場合 `CHANGELOG.md` の Unreleased に追記した
- [ ] docs を更新した（`docs/design.md` は**現在の設計だけ**を書く。経緯は ADR へ）

## 関連 issue / Related issues

Closes #
