"""レビュー用の単一HTML生成。

外部依存なし・完全自己完結（外部CDN/JS無し）の HTML を生成する。人間が
「何をどうマスクしたか」を送信前に確認するための差分＋検出根拠ビュー。

注意: 生成HTMLは原文（＝機密）を含む。mapping と同等に扱い、外部に出さないこと。
"""

from __future__ import annotations

import html
import re

from namemask.types import TYPE_LABEL_JA, MaskResult

_STYLE = """
body{font-family:system-ui,'Segoe UI',sans-serif;margin:2rem;color:#1a1a1a;line-height:1.6}
h1{font-size:1.4rem} h2{font-size:1.1rem;margin-top:1.5rem;border-bottom:1px solid #ddd}
.warn{background:#fff4e5;border:1px solid #f0b429;padding:.6rem .8rem;border-radius:6px}
pre{background:#f6f8fa;padding:.8rem;border-radius:6px;white-space:pre-wrap;word-break:break-all}
mark.m{background:#ffe08a;border-radius:3px;padding:0 2px;cursor:help}
table{border-collapse:collapse;width:100%;font-size:.92rem}
th,td{border:1px solid #ddd;padding:.35rem .5rem;text-align:left;vertical-align:top}
th{background:#f0f0f0} td.tok{font-family:ui-monospace,monospace;white-space:nowrap}
details{margin-top:1rem} summary{cursor:pointer;color:#555}
"""


def render_review_html(original: str, result: MaskResult) -> str:
    """原文と MaskResult から自己完結レビューHTMLを生成する。"""
    esc = html.escape
    items = {it.token: it for it in result.report}

    masked = esc(result.masked_text)  # トークンは ASCII なのでエスケープで不変
    if items:
        pat = re.compile("|".join(re.escape(t) for t in sorted(items, key=len, reverse=True)))

        def repl(m: re.Match) -> str:
            it = items[m.group(0)]
            label = TYPE_LABEL_JA.get(it.type, it.type)
            tip = f"元: {it.original} / 型: {label} / 根拠: {','.join(it.sources) or '-'}"
            return f'<mark class="m" title="{esc(tip)}">{esc(m.group(0))}</mark>'

        masked = pat.sub(repl, masked)

    rows = "".join(
        "<tr>"
        f"<td class=tok>{esc(it.token)}</td>"
        f"<td>{esc(TYPE_LABEL_JA.get(it.type, it.type))}</td>"
        f"<td>{esc(it.original)}</td>"
        f"<td>{esc(','.join(it.sources) or '-')}</td>"
        "</tr>"
        for it in result.report
    )
    if not rows:
        rows = "<tr><td colspan=4>（検出なし）</td></tr>"

    return (
        "<!doctype html>\n"
        '<html lang="ja"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>namemask レビュー</title>"
        f"<style>{_STYLE}</style></head><body>"
        "<h1>マスク・レビュー</h1>"
        '<p class="warn">⚠ 外部AIへ送る前に、以下の検出内容を必ず確認してください。'
        f"（{len(result.report)} 件マスク）<br>このファイルは原文を含みます。外部に出さないでください。</p>"
        "<h2>マスク済みテキスト（送信対象）</h2>"
        f'<pre class="masked">{masked}</pre>'
        "<h2>検出根拠（トークン → 原文）</h2>"
        "<table><thead><tr><th>トークン</th><th>型</th><th>原文</th><th>検出根拠</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>"
        "<details><summary>原文（参考・クリックで展開）</summary>"
        f"<pre>{esc(original)}</pre></details>"
        "</body></html>"
    )
