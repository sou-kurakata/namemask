"""ADR-0002 の帰結を固定するトリップワイヤ。

スタブ検出器（`detectors/stub.py`）は golden corpus の正解をそのまま返すため、
本番経路が誤ってスタブを選択すると、コーパス外入力に対して検出ゼロになる。
このとき round-trip テストは全て緑になる（置換が起きないので原文がそのまま
復元される）ため、既存のテスト群はこの障害を検知できない。

スタブが本番経路に混入しないことは、下記の実装上の性質に依存している。

1. `pipeline/build.py` の層テーブルがハードコードされた dict で、`layers` 引数は
   名前からクラスを引く検索ではなく既知の層への部分集合フィルタであること
2. 公開 API `mask_text` に検出器の注入口がないこと
3. 検出器を登録する entry_points が存在しないこと

意図的に設計を変更してこのテストが落ちた場合、テストを直す前に
`docs/adr/0002-build-eval-harness-and-core-before-detectors.md` の
見直し条件を参照すること。
"""

from __future__ import annotations

import inspect
import itertools

import pytest

from namemask.api import mask_text
from namemask.pipeline.build import build_default_pipeline, make_pipeline
from namemask.types import SOURCE_PRIORITY


@pytest.mark.parametrize("use_ner,use_address", list(itertools.product([True, False], repeat=2)))
def test_default_pipeline_layers_exact(use_ner: bool, use_address: bool) -> None:
    """既定パイプラインの層構成を完全一致で固定する（性質1）。

    「stub が入らない」を否定形で書くと、パイプラインが空集合を返す退行を
    見逃す。空パイプライン＝検出ゼロは、まさにここで防ぎたい障害そのもの
    なので、完全一致で書いて stub 非混入をその系として得る。
    """
    expected = {"regex", "structural", "denylist"}
    if use_ner:
        expected.add("ner")
    if use_address:
        expected.add("address")

    detectors = build_default_pipeline(use_ner=use_ner, use_address=use_address)
    assert {d.name for d in detectors} == expected


@pytest.mark.parametrize("bad", ["stub", "reges", ""])
def test_unknown_layer_name_raises(bad: str) -> None:
    """未知の層名は黙って無視せず例外にする（性質1）。

    部分集合フィルタは未知名を落とすだけなので、typo 一つで検出ゼロの
    マスカーが手に入ってしまう。不変条件2（recall 最優先）に照らして、
    ここは fail-fast でなければならない。
    """
    with pytest.raises(ValueError, match=bad or "layers"):
        build_default_pipeline(layers={bad})


def test_partially_unknown_layer_names_raise() -> None:
    """既知名に紛れた typo も検知する。"""
    with pytest.raises(ValueError, match="typo"):
        build_default_pipeline(layers={"regex", "typo"})


def test_empty_layer_selection_raises() -> None:
    """層が1つも残らない指定は例外にする。

    未知名の検査だけでは `layers={"ner"}`（use_ner=False）のような
    「既知だが無効」の指定で空パイプラインが作れてしまう。
    """
    with pytest.raises(ValueError):
        build_default_pipeline(layers=set())
    with pytest.raises(ValueError):
        build_default_pipeline(layers={"ner"}, use_ner=False)


@pytest.mark.parametrize("bad", ["denylistt", "stub"])
def test_unknown_disabled_layer_raises(bad: str) -> None:
    """`disabled` の typo も例外にする。

    こちらは黙って no-op するため検出は減らない（漏洩しない）が、
    eval のアブレーションが「この層を抜いても指標が変わらない」という
    偽の測定値を出す。ADR-0002 の主題は eval を基準線にすることなので、
    測定の完全性のためにここも fail-fast にする。
    """
    with pytest.raises(ValueError, match=bad):
        make_pipeline(disabled=bad)


def test_mask_text_signature_frozen() -> None:
    """公開 API に検出器の注入口が増えていないことを固定する（性質2）。

    「detectors という名前がない」ではなくパラメータ集合の完全一致で見る。
    `detector_override` のような別名で穴が開くのを防ぐため。
    `llm_client` は注入口だが、LLM 層は追加専用（不変条件5）でマスクの
    解除ができないため、検出ゼロを作る経路にはならない。
    """
    params = set(inspect.signature(mask_text).parameters)
    assert params == {
        "text",
        "config",
        "clients_csv",
        "use_ner",
        "use_llm",
        "use_address",
        "llm_client",
    }


def test_no_detector_entry_points() -> None:
    """検出器のプラグイン登録機構が存在しないことを固定する（性質3）。

    このグループ名は現在どこでも使っていない。将来この名前でプラグイン機構を
    導入したらこのテストが落ちる、という向きの検査であり、落ちること自体が
    ADR-0002 の見直しトリガになる。
    """
    from importlib.metadata import entry_points

    assert not list(entry_points(group="namemask.detectors"))


def test_stub_has_no_source_priority() -> None:
    """混入時の被害を抑える多層防御（`merger.py` は未登録ソースを 0 として扱う）。

    stub は golden/round-trip/eval のいずれでも単独で走り、実検出器と型競合を
    起こす場面がない。したがって優先度を持たせる理由がなく、万一混入した場合に
    他層に勝たないよう登録しない。
    """
    assert "stub" not in SOURCE_PRIORITY
