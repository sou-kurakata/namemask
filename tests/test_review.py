"""レビューHTML生成のテスト（Planv2 §11 P7）— 依存なし・常時実行。"""

from __future__ import annotations

from namemask.review import render_review_html
from namemask.types import EntityType, MaskResult, ReportItem


def _result(original_surface: str = "アオヤマ商事") -> MaskResult:
    return MaskResult(
        masked_text="[[組織_1]]の[[人名_1]]です",
        mapping={"[[組織_1]]": original_surface, "[[人名_1]]": "山田"},
        report=[
            ReportItem(original_surface, "[[組織_1]]", EntityType.ORGANIZATION,
                       ("denylist", "structural")),
            ReportItem("山田", "[[人名_1]]", EntityType.PERSON, ("structural",)),
        ],
    )


def test_html_contains_masked_marks_and_report() -> None:
    html = render_review_html("株式会社アオヤマ商事の山田です", _result())
    assert "<mark" in html                 # マスク箇所ハイライト
    assert "[[組織_1]]" in html
    assert "検出根拠" in html               # レポート表
    assert "denylist,structural" in html    # sources 表示
    assert "組織" in html and "人名" in html  # 日本語ラベル


def test_html_escapes_injection() -> None:
    # 原文由来のHTML特殊文字はエスケープされ、生タグとして出力されない。
    html = render_review_html("<b>元</b>", _result(original_surface="<script>x</script>"))
    assert "<script>x</script>" not in html
    assert "&lt;script&gt;" in html
    assert "<b>元</b>" not in html
    assert "&lt;b&gt;" in html


def test_html_is_self_contained() -> None:
    html = render_review_html("x", _result())
    assert html.strip().startswith("<!doctype html>")
    assert "http://" not in html and "https://" not in html  # 外部参照なし
    assert "<style>" in html


def test_html_no_detections() -> None:
    empty = MaskResult(masked_text="なにもない", mapping={}, report=[])
    html = render_review_html("なにもない", empty)
    assert "検出なし" in html
