"""mapping 暗号化のテスト（Planv2 §6.3 / §11 P7）。

is_encrypted の平文判定は常に実行。暗号化ラウンドトリップは cryptography 導入時のみ。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from namemask.core import crypto
from namemask.core.mapping import MappingStore


def test_is_encrypted_false_on_plaintext() -> None:
    assert not crypto.is_encrypted('{"[[組織_1]]":"アオヤマ"}')
    assert not crypto.is_encrypted("これはJSONではない")
    assert not crypto.is_encrypted("")


pytest.importorskip("cryptography", reason="cryptography 未導入")


def test_encrypt_decrypt_roundtrip() -> None:
    obj = {"[[組織_1]]": "アオヤマ商事", "[[人名_1]]": "山田太郎"}
    token = crypto.encrypt_json(obj, "correct horse")
    assert crypto.is_encrypted(token)
    # 暗号文に生の機密が現れない
    assert "アオヤマ商事" not in token
    assert "山田太郎" not in token
    assert crypto.decrypt_json(token, "correct horse") == obj


def test_wrong_passphrase_rejected() -> None:
    token = crypto.encrypt_json({"a": "b"}, "pw1")
    with pytest.raises(ValueError):
        crypto.decrypt_json(token, "pw2")


def test_tamper_detected() -> None:
    import json

    token = crypto.encrypt_json({"a": "b"}, "pw")
    env = json.loads(token)
    env["token"] = env["token"][:-4] + "AAAA"  # 改竄
    with pytest.raises(ValueError):
        crypto.decrypt_json(json.dumps(env), "pw")


def test_mappingstore_encrypted_save_load(tmp_path: Path) -> None:
    target = tmp_path / "m.json"
    MappingStore({"[[組織_1]]": "秘密商事"}).save(target, passphrase="pw")
    raw = target.read_text(encoding="utf-8")
    assert crypto.is_encrypted(raw)
    assert "秘密商事" not in raw
    loaded = MappingStore.load(target, passphrase="pw")
    assert loaded.mapping == {"[[組織_1]]": "秘密商事"}


def test_encrypted_load_requires_passphrase(tmp_path: Path) -> None:
    target = tmp_path / "m.json"
    MappingStore({"[[組織_1]]": "秘密"}).save(target, passphrase="pw")
    with pytest.raises(ValueError):
        MappingStore.load(target)  # パスフレーズ無し
