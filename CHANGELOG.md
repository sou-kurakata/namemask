# Changelog

このプロジェクトの主要な変更を記録する。
形式は [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) に従い、
バージョニングは [Semantic Versioning](https://semver.org/spec/v2.0.0.html) に従う。

## [Unreleased]

### Added
- （ここに追記する）

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

[Unreleased]: https://github.com/sou-kurakata/namemask/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/sou-kurakata/namemask/releases/tag/v0.1.0
