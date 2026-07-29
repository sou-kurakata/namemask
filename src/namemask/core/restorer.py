"""復元エンジン — 可逆性（復路）。

外部AIが返す応答からプレースホルダを元の固有名詞に戻す。
- 長いトークンから先に置換し部分一致事故を防ぐ。
- プレースホルダ改変耐性: [会社1] 【会社_1】 [[会社 _1]] 等の揺れを寛容照合。
- 曖昧・未解決は勝手に推測せず警告のみ（生値を捏造しない）。
"""

from __future__ import annotations

import re


from namemask.types import RestoreResult

# 正準トークン `[[ラベル_番号]]` を分解する。
_CANONICAL = re.compile(r"^\[\[(?P<label>.+?)_(?P<index>\d+)\]\]$")

# 未解決検出用: プレースホルダ「らしき」もの全般を寛容に拾う。
# 括弧種（[ 【）、空白、アンダースコアの揺れを許容。
_LENIENT_ANY = re.compile(
    r"[\[【]{1,2}\s*(?P<label>[^\[\]【】_\s]+)\s*_?\s*(?P<index>\d+)\s*[\]】]{1,2}"
)


def _parse_token(token: str) -> tuple[str, int]:
    m = _CANONICAL.match(token)
    if not m:
        raise ValueError(f"not a canonical placeholder token: {token!r}")
    return m.group("label"), int(m.group("index"))


def _index_pattern(index: int) -> str:
    """番号を「半角/全角どちらの数字でも」照合する正規表現片にする。

    LLM は数字を全角化しがち（[[組織１]] 等）。桁ごとに [半角全角] クラスにする
    ことで、寛容照合が全角番号にも効く（＝復元されないのに unresolved にも載らない
    非対称の根治）。全角数字 ０-９ は U+FF10-FF19。
    """
    return "".join(f"[{d}{chr(ord(d) - 0x30 + 0xFF10)}]" for d in str(index))


def _lenient_pattern(label: str, index: int) -> re.Pattern[str]:
    return re.compile(
        r"[\[【]{1,2}\s*"
        + re.escape(label)
        + r"\s*_?\s*"
        + _index_pattern(index)
        + r"\s*[\]】]{1,2}"
    )


def unmask(text: str, mapping: dict[str, str]) -> RestoreResult:
    """mapping（token -> original）でプレースホルダを復元する。"""
    warnings: list[str] = []
    result = text

    # 既知トークンの (label, index) 集合。未解決判定に使う。
    known: set[tuple[str, int]] = set()
    parsed: list[tuple[str, str, int]] = []  # (token, label, index)
    for token in mapping:
        label, index = _parse_token(token)
        known.add((label, index))
        parsed.append((token, label, index))

    # 1) 正確一致パス: 長いトークン優先で部分一致事故を防ぐ。
    for token in sorted(mapping, key=len, reverse=True):
        result = result.replace(token, mapping[token])

    # 2) 寛容パス: 改変されて正確一致で残ったものを揺れ許容で復元。
    #    番号の大きい方を先に処理し 1 が 11 の一部に食い込むのを防ぐ。
    for token, label, index in sorted(parsed, key=lambda t: t[2], reverse=True):
        pat = _lenient_pattern(label, index)
        if pat.search(result):
            result, n = pat.subn(mapping[token], result)
            if n:
                warnings.append(
                    f"改変されたプレースホルダを寛容照合で復元しました: "
                    f"{token} (×{n})"
                )

    # 3) 未解決検出: mapping に無いプレースホルダらしき残骸を推測せず報告。
    unresolved: list[str] = []
    for m in _LENIENT_ANY.finditer(result):
        label = m.group("label")
        index = int(m.group("index"))
        if (label, index) not in known:
            frag = m.group(0)
            if frag not in unresolved:
                unresolved.append(frag)
    if unresolved:
        warnings.append(
            "mapping に対応の無い未解決プレースホルダが残っています（復元せず保持）: "
            + ", ".join(unresolved)
        )

    return RestoreResult(text=result, warnings=warnings, unresolved=unresolved)
