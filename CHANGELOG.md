# Changelog

このプロジェクトの主要な変更を記録する。
形式は [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) に従い、
バージョニングは [Semantic Versioning](https://semver.org/spec/v2.0.0.html) に従う。

## [Unreleased]

### Added
- （ここに追記する）

---

## [0.1.0] - TODO(P5-3): リリース日を入れる

初回公開リリース。

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

### Notes
- 本リリースの範囲は**検出エンジンと CLI のみ**（ADR-0011）。
  ローカルレビューUIと Windows デスクトップ版は別プロジェクト。

### 実測（決定的層＋住所層・99ケース）
- precision 1.00 / 全体 recall 97.7% / round-trip 完全一致 100%

[Unreleased]: https://github.com/sou-kurakata/namemask/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/sou-kurakata/namemask/releases/tag/v0.1.0
