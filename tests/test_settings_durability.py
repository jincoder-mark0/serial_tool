"""
설정 파일 내구성 테스트 (S-081)

## WHY
설계 점검 중 나온 결함이다. `_save_to_file`이 `json.dump`로 **대상 파일에 직접**
썼다. 쓰는 도중 전원이 나가거나 디스크가 차면 설정이 반쪽으로 남는다.
그 파일로 재기동해 봤더니:

    파일을 절반으로 절단 (2184 → 1092 바이트)
    재기동 후 theme=None, 매크로 0건
    설정 폴더의 관련 파일: ['settings.local.json']    ← 백업이 없다

`_backup_corrupted_settings`는 **스키마 검증 실패 갈래에만** 걸려 있었다. 정작
가장 흔한 손상인 "저장 중 중단되어 잘린 파일"은 파싱에서 걸려 다른 갈래로 가므로,
사용자의 매크로·포트 탭 구성이 흔적 없이 사라졌다.

(이 결함을 실증하는 과정에서 실제로 개발기의 로컬 설정이 날아갔다.)

## WHAT
* 저장이 원자적인가 — 실패해도 이전 파일이 온전히 남는가
* 저장 중에는 대상 파일이 반쪽 상태로 관찰되지 않는가
* 파싱 실패로 초기화될 때 원본이 백업으로 남는가

## HOW
실제 파일 시스템에 임시 디렉터리를 잡고, 직렬화 도중 예외를 던져 "저장 실패"를
만든다. 전원 차단을 흉내 낼 수는 없으므로, 원자성이 보장하는 성질 — **실패한
저장이 기존 파일을 훼손하지 않는다** — 를 검증한다.
"""
import json

import pytest

from core.settings_manager import SettingsManager


@pytest.fixture
def manager(tmp_path, monkeypatch):
    """임시 경로에 사용자 설정을 두는 SettingsManager."""
    SettingsManager._instance = None
    from core.resource_path import ResourcePath

    instance = SettingsManager(ResourcePath())
    monkeypatch.setattr(instance, "user_settings_path", tmp_path / "settings.json")
    yield instance
    SettingsManager._instance = None


def test_save_is_atomic_when_serialization_fails(manager, monkeypatch):
    """
    저장이 실패해도 기존 파일이 남아 있어야 한다.

    대상 파일에 직접 쓰면 이 조건이 깨진다 — 파일이 열린 순간 잘리고,
    직렬화가 중간에 죽으면 반쪽짜리가 남는다.
    """
    manager.settings = {"version": "1.0", "keep": "이 값은 살아남아야 한다"}
    manager.save_settings()
    good = manager.user_settings_path.read_text(encoding="utf-8")

    # 직렬화 도중 실패시킨다 (디스크 가득참 / 전원 차단의 대역)
    import core.settings_manager as module

    def _boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(module.json, "dump", _boom)
    manager.settings = {"version": "1.0", "keep": "새 값"}
    manager.save_settings()      # IOError를 삼키므로 예외는 밖으로 나오지 않는다

    after = manager.user_settings_path.read_text(encoding="utf-8")
    assert after == good, "저장 실패가 기존 설정 파일을 훼손했다"
    assert json.loads(after)["keep"] == "이 값은 살아남아야 한다"


def test_failed_save_leaves_no_temp_file_behind(manager, monkeypatch):
    """실패한 저장이 임시 파일을 남기면 폴더가 지저분해지고 다음 저장을 헷갈리게 한다."""
    manager.settings = {"version": "1.0"}
    manager.save_settings()

    import core.settings_manager as module

    monkeypatch.setattr(module.json, "dump", lambda *a, **k: (_ for _ in ()).throw(OSError("x")))
    manager.save_settings()

    leftovers = [f.name for f in manager.user_settings_path.parent.iterdir()
                 if f.name.endswith(".tmp")]
    assert not leftovers, f"임시 파일이 남았다: {leftovers}"


def test_truncated_settings_file_is_backed_up_before_reset(manager, tmp_path):
    """
    잘린 설정 파일은 초기화 전에 백업돼야 한다.

    이것이 결함의 핵심이다 — 백업은 스키마 검증 실패에만 걸려 있었고, 가장 흔한
    손상인 "잘린 파일"은 파싱에서 걸려 다른 갈래로 빠져 흔적 없이 사라졌다.
    """
    path = manager.user_settings_path
    manager.settings = {"version": "1.0", "macros": ["AT+MYSECRET"]}
    manager.save_settings()

    whole = path.read_text(encoding="utf-8")
    path.write_text(whole[:len(whole) // 2], encoding="utf-8")   # 저장 중 중단 흉내

    SettingsManager._instance = None
    from core.resource_path import ResourcePath
    revived = SettingsManager(ResourcePath())
    revived.user_settings_path = path
    revived.load_settings()

    backups = [f.name for f in path.parent.iterdir() if f.name.endswith(".bak")]
    assert backups, (
        f"잘린 파일이 백업 없이 사라졌다 — 폴더 내용: "
        f"{[f.name for f in path.parent.iterdir()]}"
    )
