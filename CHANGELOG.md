# Changelog

このプロジェクトの主要な変更を記録する。
形式は [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) に従い、
バージョニングは [Semantic Versioning](https://semver.org/spec/v2.0.0.html) に従う。

## [Unreleased]

### Added
- （ここに追記する）

---

## [0.1.1] - 2026-08-14

v0.1.0 のクリーン環境（Ubuntu / Python 3.11 / PyPI 版）試用で見つかった不具合のうち、
**検出ロジックに触れないもの**だけを直したパッチリリース。
検出結果・mapping の内容・round-trip の挙動は 0.1.0 と完全に同一。

### Security
- **`--html` のレビュー出力を `0600` で作成する**（#1）。
  このファイルは**原文（＝機密）をそのまま含む**が、`0644`（world-readable）で
  書かれており、同格の機密である mapping（`0600`）と保護水準が揃っていなかった。
  出力先は利用者が任意に指定でき `/tmp` のような共有ディレクトリに置かれうる。
  既存ファイルへ上書きする場合も、緩いパーミッションを引き継がないよう作り直してから書く。
  POSIX で実効（Windows は ACL 管理下）。`-o` のマスク済み出力は従来どおり既定のまま。
- 生成時の stderr 警告を mapping と同水準にした（破棄の案内を追加）。

### Added
- **`namemask --version`**（#5）。バージョンは `importlib.metadata` から取得する
  （`pyproject.toml` と二重管理しない）。不具合報告での切り分けを1コマンドで済ませるため。

### Documentation
- README / README.ja の表記ゆれの節に、**濁点・半濁点つきの半角カナが
  辞書照合の対象外である**ことを明記した（#4）。正規化を**1文字ずつ**適用する
  （座標対応を厳密に保つための設計判断）ため、原文で別々のコードポイントに
  分かれた合成列（`ﾌ` + `ﾟ`）は結合されず、`ｻﾝﾌﾟﾙ` は `サンプル` と一致しない。
  **回避策（半角カナ表記を alias に足す）を実行例つきで記載。**
  実装での吸収は v0.2.0 の議題。
- `docs/security.md` の T3（`--html` レビューページ）を実装に合わせて更新。

### Known issues（このリリースでは直していない）
検出ロジックの変更を伴うため v0.2.0 の議題（凍結中）。
いずれも**部分マスク**（マスク済みに見えて一部が原文のまま残る）になる。

- 姓と名の間に空白があると人名が検出されない（`田中 太郎 様`）— #2
- ひらがなを含む地名で住所が途中で切れる（`東京都千代田区丸の内1-9-2`）— #3
- 濁点つき半角カナが辞書とマッチしない — #4

---

## [0.1.0] - 2026-08-14

初回公開リリース。**日本語のビジネス文書を外部AIへ渡す前にローカルで仮名化し、
応答を元の固有名詞へ復元する**ための検出エンジンと CLI。

### Added
- 決定的検出パイプライン: 正規化（NFKC影テキスト＋charmap逆変換）、
  正規表現層（EMAIL / PHONE / MYNUMBER・チェックディジット検証）、
  構造ルール層（法人格ORG／敬称アンカー人名）、
  辞書層（バリアント展開＋Aho-Corasick）、住所層（郵便番号・都道府県起点）
- スパン統合層（境界拡張・重複マージ・型優先度解決・ORGコア名伝播）
- 置換 / 復元エンジン（同一表記=同一トークン、プレースホルダ改変耐性）
- CLI: `namemask mask` / `unmask` / `wipe`
- ライブラリAPI: `mask_text()` / `unmask_text()`
- mapping の AES 認証暗号保存（`--encrypt`・Fernet + Scrypt）
- レビュー用の単一HTML出力（`--html`）
- optional: NER層（GiNZA・追加専用・fail-safe・既定off）
- optional: LLM検証パス（Ollama・追加専用・ループバック限定・既定off）
- golden corpus 99ケース（架空名のみ）と評価ハーネス（`tests/eval.py`）
- 型情報の同梱（`py.typed`）。公開 API は型注釈付き

### Notes
- 本リリースの範囲は**検出エンジンと CLI のみ**（ADR-0011）。
  ローカルレビューUIと Windows デスクトップ版は別プロジェクト。
- **外部通信ゼロ・telemetry なし。** 送信は利用者のコピー＆ペーストで行う
  （「マスクして送信」する動線は意図的に持たない）。
  LLM 検証パスのエンドポイントはループバック限定。
- **Python 3.10 / 3.11 / 3.12 / 3.13、Linux / macOS / Windows** で CI がテストする。
  テキストの入出力は経路によらず UTF-8 固定・改行コードは原文のまま
  （ロケールや OS で結果が変わらない）。
- mapping は生の機密。ライブラリ API は既定でメモリ内のみ、CLI は保存時に
  ディレクトリ 0700 / ファイル 0600（POSIX で実効）と stderr 警告。

### 実測（決定的層＋住所層・99ケース・NER / LLM off）
- precision 1.00 / 全体 recall 97.7%（partial 基準）/ round-trip 完全一致 100%
- 内訳: 辞書登録済み取引先 100% / 正規表現対象 100% / 法人格を含む組織名 100% /
  住所・郵便番号 100%（`--address` 指定時）
- **これらは CI の閾値ゲートで検査する**（下回るとビルドが落ちる）。
  数値と見逃しの全明細は
  [`docs/accuracy.md`](https://github.com/sou-kurakata/namemask/blob/main/docs/accuracy.md)
  に `make eval` が生成する。

### Known limitations
- **recall 100% は保証しない。** 敬称の付かない署名ブロックの人名と、
  法人格を持たず辞書にも無い会社名は決定的層では取れない（実測の見逃し6件がこれ）。
  取引先辞書への登録、または optional な NER 層で補う。
- **日本語専用。** 構造ルール層・辞書層は日本語の表記と商習慣に依存する。
- `--address` は opt-in。付けないと住所・郵便番号はマスクされない
  （全体 recall は 95.9% に下がる）。

[Unreleased]: https://github.com/sou-kurakata/namemask/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/sou-kurakata/namemask/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/sou-kurakata/namemask/releases/tag/v0.1.0
