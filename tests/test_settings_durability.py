"""
설정 파일 내구성 테스트 (S-081)

## WHY
설정 저장 중 전원 차단/디스크 오류가 발생해도 기존 사용자 설정이 손상되면 안 된다.
또한 잘린 설정 파일을 다음 실행에서 감지했을 때 원본 흔적을 backup으로 남겨야 한다.

## WHAT
* 저장 실패 시 기존 파일 보존
* 실패한 temporary file cleanup
* truncated settings parse failure 시 backup 후 fallback 복구

## HOW
실제 tmp_path filesystem에서 독립 SettingsManager instance를 사용한다.
Singleton reset 없이 새 instance를 생성해 재기동 상황을 재현한다.
"""

import json

import pytest

from core.resource_path import ResourcePath
from core.settings_manager import SettingsManager


@pytest.fixture
def manager(tmp_path, monkeypatch):
    """임시 사용자 설정 파일을 사용하는 독립 SettingsManager instance."""
    instance = SettingsManager(ResourcePath())
    monkeypatch.setattr(instance, "user_settings_path", tmp_path / "settings.json")
    yield instance


def test_save_is_atomic_when_serialization_fails(manager, monkeypatch):
    """저장이 실패해도 기존 설정 파일은 온전히 남아야 한다."""
    manager.settings = {"version": "1.0", "keep": "이 값은 살아남아야 한다"}
    manager.save_settings()
    good = manager.user_settings_path.read_text(encoding="utf-8")

    import core.settings_manager as module

    def _boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(module.json, "dump", _boom)
    manager.settings = {"version": "1.0", "keep": "새 값"}
    manager.save_settings()

    after = manager.user_settings_path.read_text(encoding="utf-8")
    assert after == good, "저장 실패가 기존 설정 파일을 훼손했다"
    assert json.loads(after)["keep"] == "이 값은 살아남아야 한다"


def test_failed_save_leaves_no_temp_file_behind(manager, monkeypatch):
    """실패한 저장은 .tmp residue를 남기지 않아야 한다."""
    manager.settings = {"version": "1.0"}
    manager.save_settings()

    import core.settings_manager as module

    monkeypatch.setattr(
        module.json,
        "dump",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("x")),
    )
    manager.save_settings()

    leftovers = [
        file.name
        for file in manager.user_settings_path.parent.iterdir()
        if file.name.endswith(".tmp")
    ]
    assert not leftovers, f"임시 파일이 남았다: {leftovers}"


def test_truncated_settings_file_is_backed_up_before_reset(manager, tmp_path):
    """잘린 설정 파일은 fallback 초기화 전에 backup으로 보존되어야 한다."""
    path = manager.user_settings_path
    manager.settings = {"version": "1.0", "macros": ["AT+MYSECRET"]}
    manager.save_settings()

    whole = path.read_text(encoding="utf-8")
    path.write_text(whole[: len(whole) // 2], encoding="utf-8")

    # 새 instance가 새 application run을 의미한다. Singleton reset은 필요하지 않다.
    revived = SettingsManager(ResourcePath())
    revived.user_settings_path = path
    revived.load_settings()

    backups = [file.name for file in path.parent.iterdir() if file.name.endswith(".bak")]
    assert backups, (
        "잘린 파일이 백업 없이 사라졌다 — 폴더 내용: "
        f"{[file.name for file in path.parent.iterdir()]}"
    )
