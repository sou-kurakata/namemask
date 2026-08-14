"""CLI テスト（Planv2 §11 P5）。決定的層のみ（--no-ner）で高速・決定的に検証。"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from namemask.cli import main

TEXT = "株式会社アオヤマ商事の山田様より、03-1234-5678でご連絡いただきました。"


def _mask(tmp_path: Path, clients_csv: str, text: str = TEXT) -> tuple[Path, Path]:
    src = tmp_path / "in.txt"
    src.write_text(text, encoding="utf-8")
    masked = tmp_path / "masked.txt"
    mapping = tmp_path / "map.json"
    rc = main(
        [
            "mask",
            str(src),
            "--no-ner",
            "--clients",
            clients_csv,
            "-o",
            str(masked),
            "-m",
            str(mapping),
        ]
    )
    assert rc == 0
    return masked, mapping


def test_mask_writes_masked_and_mapping(tmp_path: Path, clients_csv: str, capsys) -> None:
    masked, mapping = _mask(tmp_path, clients_csv)
    out = masked.read_text(encoding="utf-8")
    assert "[[組織_1]]" in out
    assert "[[人名_1]]" in out
    assert "[[電話_1]]" in out
    assert "アオヤマ商事" not in out  # 原文の機密は残らない
    assert mapping.exists()
    # レポート（検出根拠）は stderr に出る
    err = capsys.readouterr().err
    assert "マスク結果" in err
    assert "denylist" in err  # sources 表示


def test_cli_roundtrip(tmp_path: Path, clients_csv: str) -> None:
    masked, mapping = _mask(tmp_path, clients_csv)
    restored = tmp_path / "restored.txt"
    rc = main(["unmask", str(masked), "-m", str(mapping), "-o", str(restored)])
    assert rc == 0
    assert restored.read_text(encoding="utf-8") == TEXT


def test_cli_roundtrip_with_mutated_placeholders(tmp_path: Path, clients_csv: str) -> None:
    masked, mapping = _mask(tmp_path, clients_csv)
    mutated = masked.read_text(encoding="utf-8").replace("[[", "【").replace("]]", "】")
    resp = tmp_path / "resp.txt"
    resp.write_text(mutated, encoding="utf-8")
    restored = tmp_path / "restored.txt"
    rc = main(["unmask", str(resp), "-m", str(mapping), "-o", str(restored)])
    assert rc == 0
    assert restored.read_text(encoding="utf-8") == TEXT


def test_unmask_wipe_removes_mapping(tmp_path: Path, clients_csv: str) -> None:
    masked, mapping = _mask(tmp_path, clients_csv)
    rc = main(["unmask", str(masked), "-m", str(mapping), "-o", str(tmp_path / "r.txt"), "--wipe"])
    assert rc == 0
    assert not mapping.exists()


def test_wipe_subcommand(tmp_path: Path, clients_csv: str) -> None:
    _, mapping = _mask(tmp_path, clients_csv)
    assert mapping.exists()
    rc = main(["wipe", "-m", str(mapping)])
    assert rc == 0
    assert not mapping.exists()


def test_unmask_missing_mapping_errors(tmp_path: Path) -> None:
    resp = tmp_path / "r.txt"
    resp.write_text("[[組織_1]]です", encoding="utf-8")
    rc = main(["unmask", str(resp), "-m", str(tmp_path / "nope.json")])
    assert rc == 2


def test_no_save_skips_mapping_file(tmp_path: Path, clients_csv: str) -> None:
    src = tmp_path / "in.txt"
    src.write_text(TEXT, encoding="utf-8")
    mapping = tmp_path / "map.json"
    rc = main(
        [
            "mask",
            str(src),
            "--no-ner",
            "--clients",
            clients_csv,
            "-o",
            str(tmp_path / "m.txt"),
            "-m",
            str(mapping),
            "--no-save",
        ]
    )
    assert rc == 0
    assert not mapping.exists()


def test_mapping_file_is_restrictive(tmp_path: Path) -> None:
    """mapping は 0o600 で作成される（§9 ハードニング・POSIX で実効検証）。"""
    import os

    from namemask.core.mapping import MappingStore

    target = tmp_path / "sess" / "mapping.json"
    saved = MappingStore({"[[組織_1]]": "秘密"}).save(target)
    assert saved.exists()
    if os.name == "posix":
        assert (saved.stat().st_mode & 0o777) == 0o600
        assert (saved.parent.stat().st_mode & 0o777) == 0o700


def test_mask_html_review(tmp_path: Path, clients_csv: str) -> None:
    src = tmp_path / "in.txt"
    src.write_text(TEXT, encoding="utf-8")
    html = tmp_path / "review.html"
    rc = main(
        [
            "mask",
            str(src),
            "--no-ner",
            "--clients",
            clients_csv,
            "-o",
            str(tmp_path / "m.txt"),
            "-m",
            str(tmp_path / "map.json"),
            "--html",
            str(html),
        ]
    )
    assert rc == 0
    doc = html.read_text(encoding="utf-8")
    assert doc.startswith("<!doctype html>")
    assert "[[組織_1]]" in doc and "検出根拠" in doc


def test_html_review_file_is_restrictive(tmp_path: Path, clients_csv: str) -> None:
    """--html の出力は原文を含む機密なので 0o600 で作成される（mapping と同格・issue #1）。

    `-o` のマスク済み出力は外部AIへ渡す前提の成果物なので既定のままでよい。
    ここで守るのは「原文を含むファイル」だけ。
    """
    import os

    src = tmp_path / "in.txt"
    src.write_text(TEXT, encoding="utf-8")
    html = tmp_path / "review.html"
    rc = main(
        [
            "mask",
            str(src),
            "--no-ner",
            "--clients",
            clients_csv,
            "-o",
            str(tmp_path / "m.txt"),
            "-m",
            str(tmp_path / "map.json"),
            "--html",
            str(html),
        ]
    )
    assert rc == 0
    assert html.exists()
    if os.name == "posix":
        assert (html.stat().st_mode & 0o777) == 0o600


def test_html_review_does_not_inherit_loose_permissions(tmp_path: Path, clients_csv: str) -> None:
    """既に 0o644 で存在するファイルへ上書きしても、緩いままにしない（mapping と同じ）。

    open() の O_CREAT モードは既存ファイルには適用されないので、
    作り直さないとこの経路だけ 0o644 のまま原文が書き込まれる。
    """
    import os

    if os.name != "posix":
        pytest.skip("パーミッションは POSIX でのみ実効")

    src = tmp_path / "in.txt"
    src.write_text(TEXT, encoding="utf-8")
    html = tmp_path / "review.html"
    html.write_text("古い内容", encoding="utf-8")
    os.chmod(html, 0o644)

    rc = main(
        [
            "mask",
            str(src),
            "--no-ner",
            "--clients",
            clients_csv,
            "-o",
            str(tmp_path / "m.txt"),
            "-m",
            str(tmp_path / "map.json"),
            "--html",
            str(html),
        ]
    )
    assert rc == 0
    assert (html.stat().st_mode & 0o777) == 0o600


def test_version_flag_prints_version(capsys) -> None:
    """`namemask --version` が動く（issue #5）。

    サブコマンドは required だが、version アクションはその検査より先に終了する。
    バグ報告でバージョンを1コマンドで確認できることが目的。
    """
    from importlib.metadata import version as _pkg_version

    with pytest.raises(SystemExit) as e:
        main(["--version"])
    assert e.value.code == 0
    out = capsys.readouterr().out
    assert out.strip() == f"namemask {_pkg_version('namemask')}"


def test_mask_encrypt_requires_env(tmp_path: Path, clients_csv: str, monkeypatch) -> None:
    monkeypatch.delenv("NAMEMASK_PASSPHRASE", raising=False)
    src = tmp_path / "in.txt"
    src.write_text(TEXT, encoding="utf-8")
    rc = main(
        [
            "mask",
            str(src),
            "--no-ner",
            "--clients",
            clients_csv,
            "-o",
            str(tmp_path / "m.txt"),
            "-m",
            str(tmp_path / "map.json"),
            "--encrypt",
        ]
    )
    assert rc == 2  # パスフレーズ未設定はエラー


def test_cli_encrypted_roundtrip(tmp_path: Path, clients_csv: str, monkeypatch) -> None:
    pytest.importorskip("cryptography")
    monkeypatch.setenv("NAMEMASK_PASSPHRASE", "s3cret-pass")
    src = tmp_path / "in.txt"
    src.write_text(TEXT, encoding="utf-8")
    masked = tmp_path / "masked.txt"
    mapping = tmp_path / "map.json"
    assert (
        main(
            [
                "mask",
                str(src),
                "--no-ner",
                "--clients",
                clients_csv,
                "-o",
                str(masked),
                "-m",
                str(mapping),
                "--encrypt",
            ]
        )
        == 0
    )
    raw = mapping.read_text(encoding="utf-8")
    assert "アオヤマ商事" not in raw  # 平文で機密が残らない
    restored = tmp_path / "restored.txt"
    assert main(["unmask", str(masked), "-m", str(mapping), "-o", str(restored)]) == 0
    assert restored.read_text(encoding="utf-8") == TEXT


def test_crlf_line_endings_survive_roundtrip(tmp_path: Path, clients_csv: str) -> None:
    """CRLF の原文は CRLF のまま返る（改行コードを書き換えない・P3-1）。

    text モードの既定（newline=None）は読みで CRLF -> LF、書きで LF -> os.linesep に
    変換するため、CRLF 文書を POSIX で処理すると LF に、LF 文書を Windows で処理すると
    CRLF に化ける。バイト列で検証する（read_text は変換してしまい検出できない）。
    """
    src = tmp_path / "in.txt"
    raw = f"{TEXT}\r\n次の行も株式会社アオヤマ商事です。\r\n".encode()
    src.write_bytes(raw)
    masked = tmp_path / "masked.txt"
    mapping = tmp_path / "map.json"
    assert (
        main(
            [
                "mask",
                str(src),
                "--no-ner",
                "--clients",
                clients_csv,
                "-o",
                str(masked),
                "-m",
                str(mapping),
            ]
        )
        == 0
    )

    masked_bytes = masked.read_bytes()
    assert masked_bytes.count(b"\r\n") == 2
    assert b"\n" not in masked_bytes.replace(b"\r\n", b"")  # 裸の LF が混ざらない
    assert b"\r\r" not in masked_bytes  # CR の二重化も起きない

    restored = tmp_path / "restored.txt"
    assert main(["unmask", str(masked), "-m", str(mapping), "-o", str(restored)]) == 0
    assert restored.read_bytes() == raw


def test_lf_line_endings_are_not_converted(tmp_path: Path, clients_csv: str) -> None:
    """LF のみの原文に CR を足さない（Windows で CRLF に化けないことの防波堤）。"""
    src = tmp_path / "in.txt"
    raw = f"{TEXT}\n次の行も株式会社アオヤマ商事です。\n".encode()
    src.write_bytes(raw)
    masked = tmp_path / "masked.txt"
    mapping = tmp_path / "map.json"
    assert (
        main(
            [
                "mask",
                str(src),
                "--no-ner",
                "--clients",
                clients_csv,
                "-o",
                str(masked),
                "-m",
                str(mapping),
            ]
        )
        == 0
    )
    assert b"\r" not in masked.read_bytes()

    restored = tmp_path / "restored.txt"
    assert main(["unmask", str(masked), "-m", str(mapping), "-o", str(restored)]) == 0
    assert restored.read_bytes() == raw


def test_html_review_does_not_double_cr(tmp_path: Path, clients_csv: str) -> None:
    """CRLF 原文でもレビューHTMLの改行を二重化しない（P3-1）。"""
    src = tmp_path / "in.txt"
    src.write_bytes(f"{TEXT}\r\n2行目。\r\n".encode())
    html = tmp_path / "review.html"
    assert (
        main(
            [
                "mask",
                str(src),
                "--no-ner",
                "--clients",
                clients_csv,
                "-o",
                str(tmp_path / "m.txt"),
                "-m",
                str(tmp_path / "map.json"),
                "--html",
                str(html),
            ]
        )
        == 0
    )
    assert b"\r\r" not in html.read_bytes()


def test_stdin_stdout_pipe_preserves_crlf(tmp_path: Path, clients_csv: str) -> None:
    """パイプ経路でも改行コードを変換しない（P3-1）。

    実プロセスを起動する唯一のテスト。std ストリームの改行変換は main() を直接
    呼ぶ経路では再現しない（pytest が差し替えるため）。
    """
    import subprocess
    import sys

    raw = f"{TEXT}\r\n2行目。\r\n".encode()
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "namemask",
            "mask",
            "-",
            "--no-ner",
            "--clients",
            clients_csv,
            "-m",
            str(tmp_path / "map.json"),
            "--quiet",
        ],
        input=raw,
        capture_output=True,
        check=True,
    )
    assert proc.stdout.count(b"\r\n") == 2
    assert b"\n" not in proc.stdout.replace(b"\r\n", b"")


def test_pipe_works_under_non_utf8_locale(tmp_path: Path, clients_csv: str) -> None:
    """ロケール encoding が UTF-8 でなくてもパイプ経路が壊れないこと。

    Windows の既定ロケール（例: cp1252）では、リダイレクトされた標準入出力の
    encoding がそれになる。日本語は cp1252 で表現できないため、対策が無いと
    `type memo.txt | namemask mask -` も `namemask mask memo.txt > out.txt` も
    UnicodeDecodeError / UnicodeEncodeError で落ちる。**主要利用者が Windows**
    なので、ここは決定的に UTF-8 へ固定する。

    PYTHONIOENCODING で非 UTF-8 ロケールを模擬すれば、どの OS でも再現できる。
    """
    import os
    import subprocess
    import sys

    env = dict(os.environ, PYTHONIOENCODING="cp1252")
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "namemask",
            "mask",
            "-",
            "--no-ner",
            "--clients",
            clients_csv,
            "-m",
            str(tmp_path / "map.json"),
        ],
        input=f"{TEXT}\n".encode(),
        capture_output=True,
        env=env,
        check=True,
    )
    # マスク済みテキスト（日本語プレースホルダ）が UTF-8 のまま出ること。
    assert "[[組織_1]]".encode() in proc.stdout
    # stderr のレポートも同じく落ちない（日本語を含む）。
    assert "マスク結果".encode() in proc.stderr


def test_mask_reads_stdin(tmp_path: Path, clients_csv: str, monkeypatch) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(TEXT))
    masked = tmp_path / "m.txt"
    rc = main(
        [
            "mask",
            "-",
            "--no-ner",
            "--clients",
            clients_csv,
            "-o",
            str(masked),
            "-m",
            str(tmp_path / "map.json"),
        ]
    )
    assert rc == 0
    assert "[[組織_1]]" in masked.read_text(encoding="utf-8")
