"""M0 受け入れ基準テスト（Planv3 §5 / §9 M0 行）。

検証対象:
- paths.app_data_dir() が凍結時に %LOCALAPPDATA%\\namemask を、開発時に cwd を返す。
- 凍結時、mapping / config 雛形は app_data_dir 配下に書かれ、cwd には書かれない
  （N3: cwd 相対の書き込みは凍結ビルドでは禁止）。
- パス既定値は import 時でなく呼び出し時に解決される（ADR-106。monkeypatch が効く）。
- load_config() はファイルを書く副作用を持たない（ADR-107）。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

from namemask import paths
from namemask.cli import build_parser
from namemask.config import (
    Config,
    default_config_template,
    ensure_config_file,
    load_config,
)
from namemask.core.mapping import MappingStore


def _make_frozen(monkeypatch: pytest.MonkeyPatch, local: Path, cwd: Path) -> None:
    """凍結ビルドを模擬する: sys.frozen=True・LOCALAPPDATA 差し替え・cwd 隔離。"""
    local.mkdir(parents=True, exist_ok=True)
    cwd.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.chdir(cwd)


# --- app_data_dir の解決 ---------------------------------------------------


def test_app_data_dir_dev_mode_is_cwd(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.delattr(sys, "frozen", raising=False)
    cwd = tmp_path / "dev_cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    assert paths.app_data_dir().resolve() == cwd.resolve()


def test_app_data_dir_frozen_uses_localappdata(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    local = tmp_path / "LocalAppData"
    cwd = tmp_path / "start_cwd"
    _make_frozen(monkeypatch, local, cwd)
    assert paths.app_data_dir().resolve() == (local / "namemask").resolve()


def test_app_data_dir_frozen_without_localappdata_falls_back_to_home(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """LOCALAPPDATA が無い環境（mac / Linux）でも KeyError にせずホーム配下へ落とす。

    P3-1 のクロスプラットフォーム回帰ガード。`os.environ["LOCALAPPDATA"]` に
    戻すと非Windowsで CLI が起動不能になる。
    """
    home = tmp_path / "home"
    cwd = tmp_path / "start_cwd"
    home.mkdir()
    cwd.mkdir()
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.chdir(cwd)

    resolved = paths.app_data_dir().resolve()
    assert resolved == (home / "namemask").resolve()
    assert cwd.resolve() not in resolved.parents  # cwd には書かない（N3）


def test_paths_resolved_at_call_time_not_import(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """import 時に固定されていれば、後から frozen にしても cwd を指すはず。
    遅延解決なら LOCALAPPDATA 側を指す（ADR-106 の回帰ガード）。"""
    local = tmp_path / "LocalAppData"
    cwd = tmp_path / "start_cwd"
    _make_frozen(monkeypatch, local, cwd)
    assert paths.config_path().resolve() == (local / "namemask" / "config.yaml").resolve()
    assert paths.mapping_path().resolve() == (
        local / "namemask" / ".session" / "mapping.json"
    ).resolve()


# --- 凍結時: LOCALAPPDATA へ書き cwd へ書かない ---------------------------


def test_frozen_mapping_saved_to_localappdata_not_cwd(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    local = tmp_path / "LocalAppData"
    cwd = tmp_path / "start_cwd"
    _make_frozen(monkeypatch, local, cwd)

    store = MappingStore({"[[組織_1]]": "株式会社ABC商事"})
    saved = store.save()  # 既定パス = app_data_dir()/.session/mapping.json

    expected = local / "namemask" / ".session" / "mapping.json"
    assert saved.resolve() == expected.resolve()
    assert expected.exists()
    # cwd 側には .session を作っていないこと（N3）。
    assert not (cwd / ".session").exists()


def test_frozen_config_template_written_to_localappdata_not_cwd(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    local = tmp_path / "LocalAppData"
    cwd = tmp_path / "start_cwd"
    _make_frozen(monkeypatch, local, cwd)

    written = ensure_config_file()  # 既定 = app_data_dir()/config.yaml
    expected = local / "namemask" / "config.yaml"
    assert written.resolve() == expected.resolve()
    assert expected.exists()
    assert not (cwd / "config.yaml").exists()


# --- config 雛形の内容 -----------------------------------------------------


def test_config_template_is_valid_yaml_with_expected_defaults():
    data = yaml.safe_load(default_config_template())
    assert isinstance(data, dict)
    # Planv3 §5 で用意だけしておく口。
    assert data["security"]["encrypt_by_default"] is False
    # 既定値が Config のアクセサ既定と一致する（雛形が嘘をつかない）。
    cfg = Config(raw=data)
    assert cfg.encrypt_by_default is False
    assert cfg.denylist_min_core_len == 3
    assert cfg.llm_allow_remote is False


def test_ensure_config_file_does_not_overwrite_existing(tmp_path: Path):
    target = tmp_path / "config.yaml"
    target.write_text("denylist:\n  min_core_len: 9\n", encoding="utf-8")
    ensure_config_file(target)
    # 既存を上書きしない。
    assert "min_core_len: 9" in target.read_text(encoding="utf-8")


def test_ensure_config_file_writes_commented_template(tmp_path: Path):
    target = tmp_path / "sub" / "config.yaml"
    ensure_config_file(target)
    text = target.read_text(encoding="utf-8")
    assert target.exists()
    # 非エンジニアが読める日本語コメント入りであること（§5）。
    assert "#" in text
    assert yaml.safe_load(text) is not None


# --- encrypt_by_default アクセサ -------------------------------------------


def test_encrypt_by_default_defaults_false():
    assert Config(raw={}).encrypt_by_default is False


def test_encrypt_by_default_reads_true():
    cfg = Config(raw={"security": {"encrypt_by_default": True}})
    assert cfg.encrypt_by_default is True


# --- load_config は副作用を持たない（ADR-107）-----------------------------


def test_load_config_default_has_no_write_side_effect(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    monkeypatch.delattr(sys, "frozen", raising=False)
    cwd = tmp_path / "clean_cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)

    cfg = load_config()  # 既定パス解決も含め、書き出しの副作用を持たない。

    assert isinstance(cfg, Config)
    assert not (cwd / "config.yaml").exists()
    assert list(cwd.iterdir()) == []


# --- (1) dev の config は __file__ 起点（現行動作を維持）------------------


def _repo_config() -> Path:
    # src/namemask/paths.py → parents[2] = リポジトリルート。
    return Path(paths.__file__).resolve().parents[2] / "config.yaml"


def test_dev_config_path_is_repo_config_regardless_of_cwd(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.chdir(tmp_path)  # リポジトリルート以外の cwd
    assert paths.config_path().resolve() == _repo_config().resolve()


def test_load_config_reads_repo_config_from_foreign_cwd(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """リポジトリルート以外の cwd から呼んでもリポジトリの config.yaml が読まれる。

    Planv2 の「同梱 config を cwd 非依存で読む」挙動の回帰ガード（M0 レビュー (1)）。
    """
    repo_config = _repo_config()
    assert repo_config.exists()
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.chdir(tmp_path)

    cfg = load_config()

    assert cfg.raw != {}  # 空 Config でなく同梱 config を読めている
    assert cfg.raw == load_config(repo_config).raw


# --- (2) 解決関数は副作用を持たない ---------------------------------------


def test_resolution_functions_and_bootstrap_create_nothing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """一時 cwd で解決関数・build_parser・load_config を呼んでも何も作られない。"""
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.chdir(tmp_path)

    # パス解決関数（読むだけ・作らない）
    paths.app_data_dir()
    paths.config_path()
    paths.session_dir()
    paths.mapping_path()
    paths.log_dir()
    # 起動時に走る配線
    build_parser()
    load_config()

    assert list(tmp_path.iterdir()) == []


# --- (3) 雛形の機械検証 ----------------------------------------------------


def test_config_template_values_match_config_defaults():
    """雛形の各値が Config アクセサの既定値と一致する（雛形が嘘をつかない）。"""
    templated = Config(raw=yaml.safe_load(default_config_template()))
    default = Config(raw={})
    for attr in (
        "person_max_len",
        "person_stopwords",
        "org_name_max_len",
        "denylist_min_core_len",
        "clients_csv",
        "persons_csv",
        "regex_extra_patterns",
        "llm_enabled",
        "llm_endpoint",
        "llm_allow_remote",
        "llm_model",
        "llm_chunk_chars",
        "llm_timeout_sec",
        "encrypt_by_default",
    ):
        assert getattr(templated, attr) == getattr(default, attr), attr


def test_config_template_renders_unc_path_example():
    """UNC パス例が \\\\server\\... 形にレンダリングされること。"""
    text = default_config_template()
    assert r"\\server\tools\namemask\clients.csv" in text
