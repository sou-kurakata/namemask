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
    rc = main([
        "mask", str(src), "--no-ner", "--clients", clients_csv,
        "-o", str(masked), "-m", str(mapping),
    ])
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
    rc = main(["unmask", str(masked), "-m", str(mapping),
               "-o", str(tmp_path / "r.txt"), "--wipe"])
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
    rc = main(["mask", str(src), "--no-ner", "--clients", clients_csv,
               "-o", str(tmp_path / "m.txt"), "-m", str(mapping), "--no-save"])
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
    rc = main(["mask", str(src), "--no-ner", "--clients", clients_csv,
               "-o", str(tmp_path / "m.txt"), "-m", str(tmp_path / "map.json"),
               "--html", str(html)])
    assert rc == 0
    doc = html.read_text(encoding="utf-8")
    assert doc.startswith("<!doctype html>")
    assert "[[組織_1]]" in doc and "検出根拠" in doc


def test_mask_encrypt_requires_env(tmp_path: Path, clients_csv: str, monkeypatch) -> None:
    monkeypatch.delenv("NAMEMASK_PASSPHRASE", raising=False)
    src = tmp_path / "in.txt"
    src.write_text(TEXT, encoding="utf-8")
    rc = main(["mask", str(src), "--no-ner", "--clients", clients_csv,
               "-o", str(tmp_path / "m.txt"), "-m", str(tmp_path / "map.json"),
               "--encrypt"])
    assert rc == 2  # パスフレーズ未設定はエラー


def test_cli_encrypted_roundtrip(tmp_path: Path, clients_csv: str, monkeypatch) -> None:
    pytest.importorskip("cryptography")
    monkeypatch.setenv("NAMEMASK_PASSPHRASE", "s3cret-pass")
    src = tmp_path / "in.txt"
    src.write_text(TEXT, encoding="utf-8")
    masked = tmp_path / "masked.txt"
    mapping = tmp_path / "map.json"
    assert main(["mask", str(src), "--no-ner", "--clients", clients_csv,
                 "-o", str(masked), "-m", str(mapping), "--encrypt"]) == 0
    raw = mapping.read_text(encoding="utf-8")
    assert "アオヤマ商事" not in raw  # 平文で機密が残らない
    restored = tmp_path / "restored.txt"
    assert main(["unmask", str(masked), "-m", str(mapping), "-o", str(restored)]) == 0
    assert restored.read_text(encoding="utf-8") == TEXT


def test_mask_reads_stdin(tmp_path: Path, clients_csv: str, monkeypatch) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(TEXT))
    masked = tmp_path / "m.txt"
    rc = main(["mask", "-", "--no-ner", "--clients", clients_csv,
               "-o", str(masked), "-m", str(tmp_path / "map.json")])
    assert rc == 0
    assert "[[組織_1]]" in masked.read_text(encoding="utf-8")
