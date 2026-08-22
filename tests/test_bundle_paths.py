"""
번들(PyInstaller) 모드 로그 경로 테스트 모듈 (S-029)

## WHY
* 번들 실행 시 `logs_dir`가 설치 폴더(`sys._MEIPASS`, onedir의 `_internal\\`) 하위를
  가리키면 Program Files 등 읽기 전용 위치에서 로그 기록이 실패한다.
* S-013(`user_config_dir`)과 동일한 패턴으로 APPDATA 하위에 분리해야 한다.

## WHAT
* 개발 모드: `logs_dir`가 기존과 동일하게 `base_dir/'logs'`를 가리키는지(회귀 방지).
* 번들 모드: `logs_dir`가 `user_config_dir/'logs'`(APPDATA 하위)를 가리키는지.

## HOW
* `sys.frozen`, `APPDATA` 환경변수를 monkeypatch하여 두 모드를 재현한다
  (S-013의 `tests/test_core_refinement.py` monkeypatch 패턴 재사용).

pytest tests/test_bundle_paths.py -v
"""
import sys
from pathlib import Path

from core.resource_path import ResourcePath


class TestBundleLogPath:
    """S-029: 번들 모드 로그 경로가 사용자 디렉터리(APPDATA)를 가리키는지 검증합니다."""

    def test_dev_mode_logs_dir_unchanged(self, tmp_path):
        """
        개발 모드(sys.frozen 미설정)에서는 logs_dir가 기존과 동일하게
        base_dir/'logs'를 가리켜야 한다(회귀 방지).

        Logic:
            - 개발 모드 그대로(ResourcePath, sys.frozen 미설정)로 초기화
            - logs_dir == base_dir / 'logs' 확인
        """
        resource_path = ResourcePath(tmp_path)

        assert resource_path.logs_dir == tmp_path / 'logs'

    def test_frozen_mode_logs_dir_uses_appdata(self, tmp_path, monkeypatch):
        """
        번들 실행(sys.frozen=True) 시 logs_dir가 user_config_dir(APPDATA/SerialTool)
        하위 'logs'를 가리키는지 검증한다.

        Logic:
            - sys.frozen=True, APPDATA 환경변수를 임시 경로로 patch
            - ResourcePath.logs_dir가 <APPDATA>/SerialTool/logs 인지 확인
        """
        fake_appdata = tmp_path / "AppData" / "Roaming"
        monkeypatch.setattr(sys, 'frozen', True, raising=False)
        monkeypatch.setenv('APPDATA', str(fake_appdata))

        resource_path = ResourcePath(tmp_path)

        expected = fake_appdata / 'SerialTool' / 'logs'
        assert resource_path.logs_dir == expected

    def test_frozen_mode_appdata_missing_falls_back_to_home(self, tmp_path, monkeypatch):
        """
        번들 실행인데 APPDATA 환경변수가 없는 예외 상황에서
        홈 디렉터리 하위 .serial_tool/logs로 폴백하는지 검증한다.

        Logic:
            - sys.frozen=True, APPDATA 환경변수 제거
            - Path.home()을 tmp_path로 patch
            - logs_dir == tmp_path / '.serial_tool' / 'logs' 확인
        """
        monkeypatch.setattr(sys, 'frozen', True, raising=False)
        monkeypatch.delenv('APPDATA', raising=False)
        monkeypatch.setattr(Path, 'home', classmethod(lambda cls: tmp_path))

        resource_path = ResourcePath(tmp_path)

        expected = tmp_path / '.serial_tool' / 'logs'
        assert resource_path.logs_dir == expected
