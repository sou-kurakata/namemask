"""namemask CLI。

サブコマンド:
  mask    テキストを仮名化。マスク済みを stdout、検出根拠レポートを stderr、
          mapping を .session/mapping.json へ保存（人間レビュー用）。
  unmask  外部AI応答のプレースホルダを mapping で復元。--wipe で mapping 破棄。
  wipe    mapping ファイルを破棄。

設計方針:
- マスク済みテキストは stdout のみ（パイプ可能）。レポート・警告は stderr。
- mapping は生の機密。既定は .session/ 限定・gitignore・--wipe で破棄。
- 生テキストはログに出さない（レポートは人間レビュー用に端末へ出すだけ）。
- 送信は自動化しない（人間レビュー必須）。
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_PASSPHRASE_ENV = "NAMEMASK_PASSPHRASE"


def _passphrase() -> str | None:
    return os.environ.get(_PASSPHRASE_ENV) or None

from namemask import paths
from namemask.api import mask_text, unmask_text
from namemask.core.mapping import MappingStore
from namemask.review import render_review_html
from namemask.types import TYPE_LABEL_JA, MaskResult


def _read_input(path: str | None) -> str:
    """path が None/"-" なら stdin、それ以外はファイルから UTF-8 で読む。"""
    if path is None or path == "-":
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8")


def _write_output(path: str | None, text: str) -> None:
    if path is None or path == "-":
        sys.stdout.write(text)
        if text and not text.endswith("\n"):
            sys.stdout.write("\n")
    else:
        Path(path).write_text(text, encoding="utf-8")


def _render_report(result: MaskResult) -> str:
    lines = [f"=== マスク結果: {len(result.report)} 件 ==="]
    for item in result.report:
        label = TYPE_LABEL_JA.get(item.type, item.type)
        srcs = ",".join(item.sources) if item.sources else "-"
        lines.append(
            f"  {item.token:12}  {label:6}  {item.original}   <- {srcs}"
        )
    lines.append("※ 外部AIへ送る前に、上記の検出内容を必ずレビューしてください。")
    return "\n".join(lines)


def _cmd_mask(args: argparse.Namespace) -> int:
    text = _read_input(args.input)
    result = mask_text(
        text,
        clients_csv=args.clients,
        use_ner=not args.no_ner,
        use_llm=args.llm,
        use_address=args.address,
    )
    _write_output(args.out, result.masked_text)

    if not args.no_save:
        pw = None
        if args.encrypt:
            pw = _passphrase()
            if not pw:
                print(
                    f"エラー: --encrypt には環境変数 {_PASSPHRASE_ENV} が必要です。",
                    file=sys.stderr,
                )
                return 2
        store = MappingStore(result.mapping)
        saved = store.save(args.mapping, passphrase=pw)
        enc = "（AES暗号化）" if pw else "（生の機密。復元後は `unmask --wipe` で破棄推奨）"
        print(f"mapping 保存: {saved}{enc}", file=sys.stderr)
    if args.html:
        Path(args.html).write_text(
            render_review_html(text, result), encoding="utf-8"
        )
        print(f"レビューHTML: {args.html}（原文を含む。外部に出さないこと）",
              file=sys.stderr)
    if not args.quiet:
        print(_render_report(result), file=sys.stderr)
    return 0


def _cmd_unmask(args: argparse.Namespace) -> int:
    text = _read_input(args.input)
    mapping_path = Path(args.mapping)
    if not mapping_path.exists():
        print(f"エラー: mapping が見つかりません: {mapping_path}", file=sys.stderr)
        return 2
    try:
        store = MappingStore.load(mapping_path, passphrase=_passphrase())
    except (ValueError, RuntimeError) as e:
        print(f"エラー: {e}", file=sys.stderr)
        return 2
    result = unmask_text(text, store.mapping)
    _write_output(args.out, result.text)

    if not args.quiet:
        for w in result.warnings:
            print(f"警告: {w}", file=sys.stderr)
    if args.wipe:
        store.wipe(mapping_path)
        print(f"mapping 破棄: {mapping_path}", file=sys.stderr)
    # 未解決プレースホルダがあれば非ゼロ終了（呼び出し側が検知できるように）。
    return 1 if result.unresolved else 0


def _cmd_wipe(args: argparse.Namespace) -> int:
    MappingStore().wipe(args.mapping)
    print(f"mapping 破棄: {args.mapping}", file=sys.stderr)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="namemask",
        description="完全ローカルの機密テキスト・マスキング/復元ツール",
    )
    sub = p.add_subparsers(dest="command", required=True)

    default_mapping = str(paths.mapping_path())

    m = sub.add_parser("mask", help="テキストを仮名化する")
    m.add_argument("input", nargs="?", help="入力ファイル（省略/'-' で stdin）")
    m.add_argument("-o", "--out", help="マスク済み出力先（省略で stdout）")
    m.add_argument("-m", "--mapping", default=default_mapping,
                   help="mapping 保存先（既定: app_data_dir()/.session/mapping.json）")
    m.add_argument("--clients", help="取引先マスタ CSV（省略で config 参照）")
    m.add_argument("--no-ner", action="store_true", help="NER 層を使わない")
    m.add_argument("--llm", action="store_true",
                   help="LLM 検証パス（Ollama・追加専用）を後段に付ける")
    m.add_argument("--html", help="レビュー用HTMLの出力先（原文を含む・要注意）")
    m.add_argument("--address", action="store_true",
                   help="住所・郵便番号を検出する（P7）")
    m.add_argument("--encrypt", action="store_true",
                   help=f"mapping を AES 暗号化して保存（環境変数 {_PASSPHRASE_ENV} 必須）")
    m.add_argument("--no-save", action="store_true",
                   help="mapping をファイル保存しない（メモリのみ）")
    m.add_argument("--quiet", action="store_true", help="レポートを表示しない")
    m.set_defaults(func=_cmd_mask)

    u = sub.add_parser("unmask", help="応答のプレースホルダを復元する")
    u.add_argument("input", nargs="?", help="入力ファイル（省略/'-' で stdin）")
    u.add_argument("-o", "--out", help="復元済み出力先（省略で stdout）")
    u.add_argument("-m", "--mapping", default=default_mapping,
                   help="mapping ファイル（既定: app_data_dir()/.session/mapping.json）")
    u.add_argument("--wipe", action="store_true",
                   help="復元後に mapping を破棄する")
    u.add_argument("--quiet", action="store_true", help="警告を表示しない")
    u.set_defaults(func=_cmd_unmask)

    w = sub.add_parser("wipe", help="mapping を破棄する")
    w.add_argument("-m", "--mapping", default=default_mapping,
                   help="破棄する mapping ファイル")
    w.set_defaults(func=_cmd_wipe)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
