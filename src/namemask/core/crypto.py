"""mapping 暗号化 — パスフレーズ由来の AES 認証暗号。

`cryptography` の Fernet（AES128-CBC + HMAC-SHA256、認証付き）を使い、鍵は Scrypt で
パスフレーズから導出する。ソルトは暗号文に同梱。改竄・パスフレーズ不一致は復号失敗で
検知（認証付きのため生値を推測復元しない）。

`cryptography` は任意依存。未導入で暗号化を要求されたら明確なエラーを出す
（平文フォールバックはしない＝機密の意図せぬ平文保存を防ぐ）。
"""

from __future__ import annotations

import base64
import json
import os

_MAGIC = "namemask-enc-1"
# Scrypt パラメータ（対話用途として妥当なコスト）。
_SCRYPT_N = 2 ** 14
_SCRYPT_R = 8
_SCRYPT_P = 1


def _imports():
    try:
        from cryptography.fernet import Fernet, InvalidToken
        from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
    except Exception as e:  # 未導入
        raise RuntimeError(
            "mapping の暗号化には 'cryptography' が必要です "
            "（pip install cryptography）。"
        ) from e
    return Fernet, InvalidToken, Scrypt


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    Fernet, _InvalidToken, Scrypt = _imports()
    kdf = Scrypt(salt=salt, length=32, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P)
    return base64.urlsafe_b64encode(kdf.derive(passphrase.encode("utf-8")))


def encrypt_json(obj: dict, passphrase: str) -> str:
    Fernet, _InvalidToken, _Scrypt = _imports()
    salt = os.urandom(16)
    key = _derive_key(passphrase, salt)
    token = Fernet(key).encrypt(
        json.dumps(obj, ensure_ascii=False).encode("utf-8")
    )
    envelope = {
        "magic": _MAGIC,
        "salt": base64.b64encode(salt).decode("ascii"),
        "token": token.decode("ascii"),
    }
    return json.dumps(envelope, indent=2)


def is_encrypted(text: str) -> bool:
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return False
    return isinstance(data, dict) and data.get("magic") == _MAGIC


def decrypt_json(text: str, passphrase: str) -> dict:
    Fernet, InvalidToken, _Scrypt = _imports()
    env = json.loads(text)
    salt = base64.b64decode(env["salt"])
    key = _derive_key(passphrase, salt)
    try:
        plaintext = Fernet(key).decrypt(env["token"].encode("ascii"))
    except InvalidToken as e:
        raise ValueError(
            "mapping の復号に失敗しました（パスフレーズ不一致または改竄）。"
        ) from e
    return json.loads(plaintext.decode("utf-8"))
