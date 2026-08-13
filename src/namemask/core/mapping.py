"""mapping の保存/破棄。

mapping は生の機密。既定はメモリ内。ファイル保存する場合のみ
`app_data_dir()/.session/mapping.json` に限定し、gitignore 前提。--wipe で破棄。
保存先は `paths.mapping_path()` を呼び出し時に解決する（凍結時は
`%LOCALAPPDATA%\\namemask\\.session\\`。cwd 相対の書き込みは禁止。N3 / ADR-106）。
passphrase 指定時は AES 認証暗号で保存する（core/crypto.py）。
"""

from __future__ import annotations

import contextlib
import json
import os
from pathlib import Path

from namemask import paths
from namemask.core import crypto


def _default_file() -> Path:
    """mapping.json の既定パス（app_data_dir 配下、呼び出し時解決）。"""
    return paths.mapping_path()


class MappingStore:
    """token -> original の対応表を安全に保持する。

    既定はメモリ内のみ。save() を呼んだ時だけ `.session/` に書く。
    """

    def __init__(self, mapping: dict[str, str] | None = None) -> None:
        self._mapping: dict[str, str] = dict(mapping or {})

    @property
    def mapping(self) -> dict[str, str]:
        return dict(self._mapping)

    def save(
        self, path: Path | str | None = None, passphrase: str | None = None
    ) -> Path:
        """`app_data_dir()/.session/mapping.json`（既定）へ書き出す。呼ばれた時のみ。

        passphrase を渡すと AES 認証暗号（Scrypt 鍵導出）で保存する。
        mapping は生の機密
        。同一ホストの他ユーザから読めないよう、ディレクトリ
        は 0o700、ファイルは 0o600 で作成する（POSIX で実効。Windows では ACL 制御が
        別途必要だが、少なくとも POSIX 相当環境で無防備な 0644 を避ける）。
        """
        target = Path(path) if path is not None else _default_file()
        if passphrase:
            content = crypto.encrypt_json(self._mapping, passphrase)
        else:
            content = json.dumps(self._mapping, ensure_ascii=False, indent=2)

        target.parent.mkdir(parents=True, exist_ok=True)
        # Windows など chmod が効かない環境でも保存自体は止めない。
        with contextlib.suppress(OSError):
            os.chmod(target.parent, 0o700)
        # 既存ファイルの緩いパーミッションを引き継がないよう、作り直してから書く。
        with contextlib.suppress(FileNotFoundError):
            os.remove(target)
        # O_CREAT で 0o600 を指定して作成（umask の影響を受けにくい）。
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
        finally:
            with contextlib.suppress(OSError):
                os.chmod(target, 0o600)
        return target

    @classmethod
    def load(
        cls, path: Path | str | None = None, passphrase: str | None = None
    ) -> MappingStore:
        """mapping を読み込む。暗号化ファイルなら passphrase で復号する。"""
        target = Path(path) if path is not None else _default_file()
        text = target.read_text(encoding="utf-8")
        if crypto.is_encrypted(text):
            if not passphrase:
                raise ValueError(
                    "暗号化された mapping です。パスフレーズが必要です "
                    "（環境変数 NAMEMASK_PASSPHRASE）。"
                )
            return cls(crypto.decrypt_json(text, passphrase))
        return cls(json.loads(text))

    def wipe(self, path: Path | str | None = None) -> None:
        """メモリ内 mapping を消し、保存ファイルがあれば削除する（--wipe）。"""
        self._mapping.clear()
        target = Path(path) if path is not None else _default_file()
        with contextlib.suppress(FileNotFoundError):
            os.remove(target)
