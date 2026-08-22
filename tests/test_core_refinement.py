"""
코어 로직 정밀 테스트 모듈

애플리케이션의 기반이 되는 Core 유틸리티 및 매니저 클래스를 검증합니다.

## WHY
* 데이터 변환(CommandProcessor) 오류는 통신 전체의 신뢰성을 떨어뜨림
* 이벤트 버스(EventBus) 오류는 컴포넌트 간 통신 단절을 초래함
* 설정 관리(SettingsManager) 오류는 앱 초기화 실패의 원인이 됨

## WHAT
* CommandProcessor: ASCII/HEX 변환, 접두사/접미사 처리, 에러 핸들링
* EventBus: 구독/발행 메커니즘, 토픽 라우팅, 구독 취소
* SettingsManager: 싱글톤 패턴, 설정값 읽기/쓰기 무결성

## HOW
* 다양한 입력 케이스(정상/비정상)를 통한 CommandProcessor 검증
* Mock 콜백 함수를 이용한 EventBus 메시지 전달 확인
* pytest의 tmp_path와 patch를 활용한 설정 파일 I/O 격리 테스트

pytest tests/test_core_refinement.py -v
"""
import json
import sys
from pathlib import Path

import pytest
from unittest.mock import MagicMock, patch

from core.command_processor import CommandProcessor
from core.event_bus import EventBus
from core.settings_manager import SettingsManager
from core.resource_path import ResourcePath
from common.constants import ConfigKeys


class TestCommandProcessor:
    """
    명령어 처리기(CommandProcessor)의 데이터 변환 로직을 검증합니다.
    """

    def test_process_ascii_command(self):
        """
        일반 ASCII 명령어 변환 테스트

        Logic:
            - 문자열 입력
            - HEX 모드 False
            - 바이트 변환 결과 확인 (UTF-8 인코딩)
        """
        # GIVEN: 일반 문자열
        cmd = "Hello World"

        # WHEN: 변환 수행
        result = CommandProcessor.process_command(cmd, hex_mode=False)

        # THEN: 바이트로 변환되어야 함
        assert result == b"Hello World"

    def test_process_hex_command_valid(self):
        """
        유효한 HEX 문자열 변환 테스트

        Logic:
            - 공백이 포함된 HEX 문자열 입력 ("AA BB")
            - HEX 모드 True
            - 바이너리 데이터 변환 확인
        """
        # GIVEN: HEX 문자열 (대소문자 혼용, 공백 포함)
        cmd = "AA bb 01"

        # WHEN: 변환 수행
        result = CommandProcessor.process_command(cmd, hex_mode=True)

        # THEN: 정확한 바이트 값이어야 함
        assert result == b'\xaa\xbb\x01'

    def test_process_hex_command_invalid(self):
        """
        유효하지 않은 HEX 문자열 처리 테스트

        Logic:
            - HEX가 아닌 문자('G') 포함
            - HEX 모드 True
            - ValueError 발생 확인
        """
        # GIVEN: 잘못된 HEX 문자열
        cmd = "ZZ Top"

        # WHEN & THEN: 변환 시도 시 예외 발생
        with pytest.raises(ValueError):
            CommandProcessor.process_command(cmd, hex_mode=True)

    def test_process_with_prefix_suffix(self):
        """
        접두사(Prefix) 및 접미사(Suffix) 결합 테스트

        Logic:
            - 명령어, 접두사, 접미사 입력
            - 모든 요소가 결합된 바이트 데이터 반환 확인
        """
        # GIVEN: 데이터 및 설정
        cmd = "DATA"
        prefix = "<STX>"
        suffix = "<ETX>"

        # WHEN: 변환 수행
        result = CommandProcessor.process_command(
            cmd,
            hex_mode=False,
            prefix=prefix,
            suffix=suffix
        )

        # THEN: 순서대로 결합되어야 함
        assert result == b"<STX>DATA<ETX>"

    def test_process_hex_with_prefix_suffix(self):
        """
        HEX 모드에서의 접두사/접미사 결합 테스트

        Logic:
            - 접두사/접미사는 항상 문자열로 처리됨을 가정 (또는 구현에 따라 다름)
            - CommandProcessor는 Prefix/Suffix를 ASCII로 처리한다고 가정
        """
        # GIVEN
        cmd = "FF 00"
        prefix = "41"
        suffix = "42"

        # WHEN
        result = CommandProcessor.process_command(
            cmd,
            hex_mode=True,
            prefix=prefix,
            suffix=suffix
        )

        # THEN: Prefix(A) + Hex(FF 00) + Suffix(B)
        # b'A' -> 0x41, b'B' -> 0x42
        expected = b'A\xff\x00B'
        assert result == expected


class TestEventBus:
    """
    이벤트 버스(EventBus)의 발행/구독 패턴을 검증합니다.
    """

    @pytest.fixture(autouse=True)
    def clean_event_bus(self):
        """테스트 전후로 EventBus 상태를 초기화합니다."""
        bus = EventBus()
        # 내부 저장소 초기화 (Singleton이므로 필수)
        if hasattr(bus, '_subscribers'):
            bus._subscribers.clear()
        yield bus
        if hasattr(bus, '_subscribers'):
            bus._subscribers.clear()

    def test_subscribe_and_publish(self):
        """
        이벤트 구독 및 발행 성공 테스트

        Logic:
            - 특정 토픽 구독
            - 해당 토픽으로 메시지 발행
            - 콜백 함수 호출 여부 및 전달 데이터 검증
        """
        # GIVEN
        bus = EventBus()
        topic = "test_topic"
        data = {"key": "value"}

        mock_callback = MagicMock()

        # WHEN: 구독 및 발행
        bus.subscribe(topic, mock_callback)
        bus.publish(topic, data)

        # THEN: 콜백 호출 확인
        mock_callback.assert_called_once_with(data)

    def test_publish_no_subscribers(self):
        """
        구독자가 없는 토픽 발행 테스트

        Logic:
            - 구독자 없이 발행
            - 에러 없이 정상 실행되어야 함 (Silent Ignore)
        """
        # GIVEN
        bus = EventBus()
        topic = "ghost_topic"

        # WHEN & THEN: 에러 발생하지 않아야 함
        try:
            bus.publish(topic, "some_data")
        except Exception as e:
            pytest.fail(f"Publishing to no subscribers raised exception: {e}")

    def test_unsubscribe(self):
        """
        구독 취소 기능 테스트

        Logic:
            - 구독 후 발행 (호출 확인)
            - 구독 취소 후 발행 (호출 안 됨 확인)
        """
        # GIVEN
        bus = EventBus()
        topic = "status_update"
        mock_callback = MagicMock()

        bus.subscribe(topic, mock_callback)

        # WHEN: 1차 발행
        bus.publish(topic, "msg1")
        assert mock_callback.call_count == 1

        # WHEN: 구독 취소 및 2차 발행
        bus.unsubscribe(topic, mock_callback)
        bus.publish(topic, "msg2")

        # THEN: 카운트가 증가하지 않아야 함
        assert mock_callback.call_count == 1

    def test_multiple_subscribers(self):
        """
        다중 구독자 처리 테스트

        Logic:
            - 하나의 토픽에 두 개의 콜백 등록
            - 메시지 발행 시 둘 다 호출되어야 함
        """
        # GIVEN
        bus = EventBus()
        topic = "broadcast"

        sub1 = MagicMock()
        sub2 = MagicMock()

        bus.subscribe(topic, sub1)
        bus.subscribe(topic, sub2)

        # WHEN
        bus.publish(topic, "payload")

        # THEN
        sub1.assert_called_once()
        sub2.assert_called_once()


class TestSettingsManager:
    """
    설정 관리자(SettingsManager)의 저장소 로직을 검증합니다.
    """

    def test_singleton_behavior(self):
        """
        싱글톤 패턴 동작 검증

        Logic:
            - 두 번 인스턴스 생성
            - 두 객체의 아이디(메모리 주소)가 동일한지 확인
        """
        # 싱글톤 인스턴스 초기화 (테스트 격리)
        SettingsManager._instance = None

        m1 = SettingsManager()
        m2 = SettingsManager()

        assert m1 is m2

        # 정리
        SettingsManager._instance = None

    def test_get_set_value(self):
        """
        설정값 읽기 및 쓰기 테스트 (메모리 상)

        Logic:
            - 설정값 set
            - get으로 읽었을 때 일치 확인
            - 존재하지 않는 키 get 시 기본값 반환 확인
        """
        SettingsManager._instance = None
        manager = SettingsManager()

        # Mocking load/save to avoid file I/O
        with patch.object(manager, 'load_settings'), \
             patch.object(manager, 'save_settings'):

            # WHEN: 값 설정
            manager.set(ConfigKeys.PORT_BAUDRATE, 9600)

            # THEN: 값 읽기
            assert manager.get(ConfigKeys.PORT_BAUDRATE) == 9600

            # THEN: 기본값 테스트
            assert manager.get("NON_EXISTENT_KEY", "DEFAULT") == "DEFAULT"

    def test_save_triggers_file_io(self, tmp_path):
        """
        저장 시 파일 쓰기 동작 검증 (Mocking 없이 tmp_path 사용)

        Logic:
            - tmp_path를 설정 파일 경로로 패치
            - save_settings() 호출
            - 파일이 생성되고 내용이 JSON으로 기록되었는지 확인
        """
        # GIVEN: 임시 파일 경로
        test_file = tmp_path / "config.json"

        SettingsManager._instance = None

        from core.resource_path import ResourcePath

        resource_path = ResourcePath(tmp_path)
        resource_path.config_dir.mkdir(parents=True)
        resource_path.settings_file = test_file
        manager = SettingsManager(resource_path)

        manager.set("test_key", 12345)
        manager.save_settings()

        assert test_file.exists()

        import json
        with open(test_file, 'r') as f:
            data = json.load(f)
            assert data["test_key"] == 12345

    def test_dev_mode_user_settings_path_matches_config_path(self, tmp_path):
        """
        S-013 회귀 방지: 개발 모드(sys.frozen 미설정)에서는
        config_path와 user_settings_path가 완전히 동일해야 한다
        (기존 동작·테스트 완전 불변).

        Logic:
            - 개발 모드 그대로(ResourcePath, sys.frozen 미설정)로 초기화
            - config_path와 user_settings_path가 같은 경로인지 확인
        """
        SettingsManager._instance = None

        resource_path = ResourcePath(tmp_path)
        resource_path.config_dir.mkdir(parents=True)
        manager = SettingsManager(resource_path)

        assert manager.config_path == manager.user_settings_path
        assert resource_path.user_settings_file == resource_path.settings_file

        SettingsManager._instance = None

    def test_frozen_mode_user_config_dir_uses_appdata(self, tmp_path, monkeypatch):
        """
        번들 실행(sys.frozen=True) 시 user_config_dir가 APPDATA/SerialTool을
        가리키는지 검증한다.

        Logic:
            - sys.frozen=True, APPDATA 환경변수를 임시 경로로 patch
            - ResourcePath.user_config_dir가 <APPDATA>/SerialTool 인지 확인
            - 디렉터리가 실제로 생성되었는지 확인
        """
        fake_appdata = tmp_path / "AppData" / "Roaming"
        monkeypatch.setattr(sys, 'frozen', True, raising=False)
        monkeypatch.setenv('APPDATA', str(fake_appdata))

        resource_path = ResourcePath(tmp_path)

        expected = fake_appdata / 'SerialTool'
        assert resource_path.user_config_dir == expected
        assert expected.exists()
        assert resource_path.user_settings_file == expected / 'settings.json'

    def test_frozen_mode_appdata_missing_falls_back_to_home(self, tmp_path, monkeypatch):
        """
        번들 실행인데 APPDATA 환경변수가 없는 예외 상황에서
        홈 디렉터리 하위 .serial_tool로 폴백하는지 검증한다.

        Logic:
            - sys.frozen=True, APPDATA 환경변수 제거
            - Path.home()을 tmp_path로 patch
            - user_config_dir == tmp_path / '.serial_tool' 확인
        """
        monkeypatch.setattr(sys, 'frozen', True, raising=False)
        monkeypatch.delenv('APPDATA', raising=False)
        monkeypatch.setattr(Path, 'home', classmethod(lambda cls: tmp_path))

        resource_path = ResourcePath(tmp_path)

        expected = tmp_path / '.serial_tool'
        assert resource_path.user_config_dir == expected
        assert expected.exists()

    def test_frozen_mode_first_run_migrates_from_default_distribution(self, tmp_path, monkeypatch):
        """
        번들 모드 첫 실행 시나리오: 사용자 경로에 설정 파일이 없으면
        기본 배포본(resources/configs/settings.json)을 읽어 초기화하고,
        저장은 사용자 경로(APPDATA)에만 이루어져야 한다(배포본은 불변).

        Logic:
            - 기본 배포본에 식별 가능한 마커 키를 넣어 둔다
            - sys.frozen=True, APPDATA를 임시 경로로 patch
            - SettingsManager 초기화 후 사용자 경로에 파일이 생성되고
              마커 값이 반영되었는지 확인
            - 배포본 파일 내용이 변경되지 않았는지(쓰기 금지) 확인
        """
        fake_appdata = tmp_path / "AppData"
        monkeypatch.setattr(sys, 'frozen', True, raising=False)
        monkeypatch.setenv('APPDATA', str(fake_appdata))

        resource_path = ResourcePath(tmp_path)
        resource_path.config_dir.mkdir(parents=True)

        # 기본 배포본 작성 (마커 포함)
        from common.defaults import create_fallback_settings
        default_distribution = create_fallback_settings()
        default_distribution["distribution_marker"] = "from_default_distribution"
        with open(resource_path.settings_file, 'w', encoding='utf-8') as f:
            json.dump(default_distribution, f)
        original_distribution_text = resource_path.settings_file.read_text(encoding='utf-8')

        # 사용자 경로에는 아직 파일이 없어야 한다
        assert not resource_path.user_settings_file.exists()

        SettingsManager._instance = None
        manager = SettingsManager(resource_path)

        try:
            # 첫 실행 이관: 사용자 경로에 파일이 생성되고 마커가 반영됨
            assert manager.user_settings_path.exists()
            assert manager.get("distribution_marker") == "from_default_distribution"

            # 배포본 파일은 변경되지 않아야 함(쓰기 금지)
            assert resource_path.settings_file.read_text(encoding='utf-8') == original_distribution_text
        finally:
            SettingsManager._instance = None

    def test_frozen_mode_second_run_prefers_user_file(self, tmp_path, monkeypatch):
        """
        번들 모드에서 사용자 설정 파일이 이미 존재하면, 기본 배포본이 아닌
        사용자 파일을 우선 로드해야 한다.

        Logic:
            - 배포본과 사용자 경로 양쪽에 서로 다른 마커 값을 가진 설정을 배치
            - SettingsManager 초기화 후 사용자 파일의 값을 사용하는지 확인
        """
        fake_appdata = tmp_path / "AppData"
        monkeypatch.setattr(sys, 'frozen', True, raising=False)
        monkeypatch.setenv('APPDATA', str(fake_appdata))

        resource_path = ResourcePath(tmp_path)
        resource_path.config_dir.mkdir(parents=True)

        from common.defaults import create_fallback_settings

        default_distribution = create_fallback_settings()
        default_distribution["distribution_marker"] = "from_default_distribution"
        with open(resource_path.settings_file, 'w', encoding='utf-8') as f:
            json.dump(default_distribution, f)

        user_settings = create_fallback_settings()
        user_settings["distribution_marker"] = "from_user_file"
        # user_config_dir 접근 시 디렉터리가 생성됨
        user_path = resource_path.user_settings_file
        with open(user_path, 'w', encoding='utf-8') as f:
            json.dump(user_settings, f)

        SettingsManager._instance = None
        manager = SettingsManager(resource_path)

        try:
            assert manager.get("distribution_marker") == "from_user_file"
        finally:
            SettingsManager._instance = None

    def test_migration_global_and_settings_coexist_settings_wins(self, tmp_path):
        """
        S-027: 1.0 파일에 global과 settings가 공존하고 값이 다를 때,
        마이그레이션 후 settings.* 값(실사용 값)이 살아남고 global 블록은
        사라져야 한다.

        Logic:
            - version 1.0, global.theme="dark"/global.language="ko",
              settings.theme="dracula"/settings.language="en"인 파일 작성
            - SettingsManager 초기화
            - settings.theme/language가 기존 settings.* 값을 유지하는지 확인
            - global 키가 사라지고 version이 CURRENT_VERSION(1.3)인지 확인
              (S-030: CURRENT_VERSION 1.2 -> 1.3 승격에 맞춰 갱신)
        """
        SettingsManager._instance = None

        resource_path = ResourcePath(tmp_path)
        resource_path.config_dir.mkdir(parents=True)

        old_settings = {
            "version": "1.0",
            "global": {"theme": "dark", "language": "ko"},
            "settings": {"theme": "dracula", "language": "en"}
        }
        with open(resource_path.settings_file, 'w', encoding='utf-8') as f:
            json.dump(old_settings, f)

        try:
            manager = SettingsManager(resource_path)

            assert manager.get("settings.theme") == "dracula"
            assert manager.get("settings.language") == "en"
            assert manager.get("global") is None
            assert manager.get("version") == "1.3"

            # 파일에도 반영되었는지 확인
            with open(manager.user_settings_path, 'r', encoding='utf-8') as f:
                saved = json.load(f)
            assert "global" not in saved
        finally:
            SettingsManager._instance = None

    def test_migration_global_only_moves_to_settings(self, tmp_path):
        """
        S-027: global만 있고 settings가 없는 1.0 파일은 global 값이
        settings.*로 이관되어야 한다.

        Logic:
            - version 1.0, global.theme/language만 있는 파일 작성(settings 없음)
            - SettingsManager 초기화
            - settings.theme/language가 global 값과 동일한지 확인
        """
        SettingsManager._instance = None

        resource_path = ResourcePath(tmp_path)
        resource_path.config_dir.mkdir(parents=True)

        old_settings = {
            "version": "1.0",
            "global": {"theme": "light", "language": "ko"}
        }
        with open(resource_path.settings_file, 'w', encoding='utf-8') as f:
            json.dump(old_settings, f)

        try:
            manager = SettingsManager(resource_path)

            assert manager.get("settings.theme") == "light"
            assert manager.get("settings.language") == "ko"
            assert manager.get("global") is None
        finally:
            SettingsManager._instance = None

    def test_migration_removes_dead_ui_font_keys(self, tmp_path):
        """
        S-027: ui 블록의 죽은 폰트 키 4종(proportional/fixed font family/size)은
        마이그레이션 후 제거되어야 한다(실사용은 settings.* 쪽).

        Logic:
            - version 1.0, ui에 죽은 폰트 키를 포함한 파일 작성
            - SettingsManager 초기화 후 ui 블록에 해당 키들이 없는지 확인
            - max_log_lines 등 살아있는 키는 유지되는지 확인
        """
        SettingsManager._instance = None

        resource_path = ResourcePath(tmp_path)
        resource_path.config_dir.mkdir(parents=True)

        old_settings = {
            "version": "1.0",
            "global": {"theme": "dark", "language": "ko"},
            "ui": {
                "max_log_lines": 500,
                "proportional_font_family": "Segoe UI",
                "proportional_font_size": 9,
                "fixed_font_family": "Consolas",
                "fixed_font_size": 9
            }
        }
        with open(resource_path.settings_file, 'w', encoding='utf-8') as f:
            json.dump(old_settings, f)

        try:
            manager = SettingsManager(resource_path)

            ui = manager.get("ui")
            assert "proportional_font_family" not in ui
            assert "proportional_font_size" not in ui
            assert "fixed_font_family" not in ui
            assert "fixed_font_size" not in ui
            assert ui.get("max_log_lines") == 500
        finally:
            SettingsManager._instance = None

    def test_migration_v1_3_file_passes_unchanged(self, tmp_path):
        """
        S-030: 이미 1.3 버전(현재 버전)인 파일은 마이그레이션 없이 그대로 통과해야 한다.
        (S-028 당시 1.2 기준으로 작성된 테스트를 CURRENT_VERSION 1.3 승격에 맞춰 갱신)

        Logic:
            - version 1.3, settings.theme/language를 가진 정상 파일 작성
            - SettingsManager 초기화 후 값이 그대로 유지되는지 확인
            - _needs_migration이 False인지 확인(마이그레이션 미실행 방증)
        """
        from common.defaults import create_fallback_settings

        SettingsManager._instance = None

        resource_path = ResourcePath(tmp_path)
        resource_path.config_dir.mkdir(parents=True)

        current_settings = create_fallback_settings()
        current_settings["version"] = "1.3"
        current_settings["settings"] = {"theme": "dracula", "language": "en"}
        with open(resource_path.settings_file, 'w', encoding='utf-8') as f:
            json.dump(current_settings, f)

        try:
            manager = SettingsManager(resource_path)

            assert manager._needs_migration({"version": "1.3"}) is False
            assert manager.get("settings.theme") == "dracula"
            assert manager.get("settings.language") == "en"
            assert manager.get("global") is None
        finally:
            SettingsManager._instance = None

    def test_migration_v1_2_removes_orphan_serial_keeps_tab_flowctrl(self, tmp_path):
        """
        S-030: 1.2 파일의 최상위 serial 블록(고아 블록, flowctrl/flow_control 포함)은
        1.3 마이그레이션에서 완전히 제거되어야 하고, ports.tabs[*].serial.flowctrl
        (탭별 실사용 상태, 완전히 다른 데이터 경로)는 절대 건드리지 않아야 한다.

        Logic:
            - version 1.2, 최상위 serial 블록(flowctrl/flow_control 공존) +
              ports.tabs에 flowctrl을 가진 탭 상태 1개를 포함한 파일 작성
            - SettingsManager 초기화 후:
              * 최상위 serial 키가 완전히 사라졌는지 확인
              * ports.tabs[0].serial.flowctrl 값이 그대로 보존되는지 확인
              * version이 1.3으로 갱신되었는지 확인
        """
        SettingsManager._instance = None

        resource_path = ResourcePath(tmp_path)
        resource_path.config_dir.mkdir(parents=True)

        old_settings = {
            "version": "1.2",
            "settings": {"theme": "dark", "language": "ko"},
            "serial": {
                "baudrate": 115200,
                "parity": "N",
                "bytesize": 8,
                "stopbits": 1,
                "flowctrl": "None",
                "newline": "LF",
                "local_echo_enabled": False,
                "scan_interval_ms": 1000,
                "flow_control": "None"
            },
            "ports": {
                "tabs": [
                    {
                        "protocol": "Serial",
                        "port": "COM3",
                        "serial": {
                            "baudrate": "9600",
                            "bytesize": "8",
                            "parity": "N",
                            "stopbits": "1",
                            "flowctrl": "RTS/CTS"
                        }
                    }
                ]
            }
        }
        with open(resource_path.settings_file, 'w', encoding='utf-8') as f:
            json.dump(old_settings, f)

        try:
            manager = SettingsManager(resource_path)

            assert manager.get("serial") is None
            tabs = manager.get("ports.tabs")
            assert tabs[0]["serial"]["flowctrl"] == "RTS/CTS"
            assert manager.get("version") == "1.3"

            # 파일에도 반영되었는지 확인
            with open(manager.user_settings_path, 'r', encoding='utf-8') as f:
                saved = json.load(f)
            assert "serial" not in saved
            assert saved["ports"]["tabs"][0]["serial"]["flowctrl"] == "RTS/CTS"
        finally:
            SettingsManager._instance = None

    def test_defaults_have_no_orphan_serial_block(self):
        """
        S-030: create_fallback_settings()에는 더 이상 최상위 serial 블록이
        존재하지 않아야 한다 (고아 블록 완전 제거 확인 — DoD 1항).
        """
        from common.defaults import create_fallback_settings

        defaults = create_fallback_settings()

        assert "serial" not in defaults

    def test_migrate_settings_applied_to_defaults_is_noop(self):
        """
        S-030 재발 차단 (핵심 산출물, doc/mistakes.md #2 규칙화):
        create_fallback_settings()의 산출물에 _migrate_settings를 적용해도
        무변경(no-op)이어야 한다. defaults가 마이그레이션이 지운/개명한 옛 키를
        다시 갖는 순간(예: 이번 사건의 serial.flowctrl) 이 테스트가 즉시 깨진다.

        Logic:
            - create_fallback_settings()로 현재 버전 기본 설정 생성
            - _needs_migration(defaults)가 False인지 확인
            - _migrate_settings(defaults)를 적용한 결과가 원본과 완전히 동일한지 확인
        """
        from common.defaults import create_fallback_settings

        SettingsManager._instance = None
        manager = SettingsManager.__new__(SettingsManager)

        defaults = create_fallback_settings()

        assert manager._needs_migration(defaults) is False

        migrated = manager._migrate_settings(defaults)

        assert migrated == defaults

    def test_migration_v1_0_saved_right_width_not_renamed(self, tmp_path):
        """
        S-028 ①: 1.0 파일의 saved_right_section_width는 더 이상
        right_section_width로 개명되지 않고 그대로 살아남아야 한다
        (정본 키 = ui.saved_right_section_width, S-016과 동일 원칙).

        Logic:
            - version 1.0, ui.saved_right_section_width=598인 파일 작성
            - SettingsManager 초기화 후 ui.saved_right_section_width==598 유지,
              ui.right_section_width는 생기지 않아야 함
            - version이 1.3으로 갱신되었는지 확인
        """
        SettingsManager._instance = None

        resource_path = ResourcePath(tmp_path)
        resource_path.config_dir.mkdir(parents=True)

        old_settings = {
            "version": "1.0",
            "global": {"theme": "dark", "language": "ko"},
            "ui": {"saved_right_section_width": 598}
        }
        with open(resource_path.settings_file, 'w', encoding='utf-8') as f:
            json.dump(old_settings, f)

        try:
            manager = SettingsManager(resource_path)

            ui = manager.get("ui")
            assert ui.get("saved_right_section_width") == 598
            assert "right_section_width" not in ui
            assert manager.get("version") == "1.3"
        finally:
            SettingsManager._instance = None

    def test_migration_v1_1_stale_right_width_merged_and_removed(self, tmp_path):
        """
        S-028 ②: 1.1 파일에 잔존하는 ui.right_section_width는 값을
        ui.saved_right_section_width로 이어받은 뒤 삭제되어야 한다
        (saved_right_section_width가 없거나 None인 경우).

        Logic:
            - version 1.1, ui.right_section_width=651만 있고
              saved_right_section_width는 없는 파일 작성
            - SettingsManager 초기화 후 saved_right_section_width==651,
              right_section_width는 사라짐을 확인
        """
        SettingsManager._instance = None

        resource_path = ResourcePath(tmp_path)
        resource_path.config_dir.mkdir(parents=True)

        old_settings = {
            "version": "1.1",
            "settings": {"theme": "dark", "language": "ko"},
            "ui": {"right_section_width": 651}
        }
        with open(resource_path.settings_file, 'w', encoding='utf-8') as f:
            json.dump(old_settings, f)

        try:
            manager = SettingsManager(resource_path)

            ui = manager.get("ui")
            assert ui.get("saved_right_section_width") == 651
            assert "right_section_width" not in ui
            assert manager.get("version") == "1.3"
        finally:
            SettingsManager._instance = None

    def test_migration_v1_1_stale_right_width_discarded_when_saved_already_set(self, tmp_path):
        """
        S-028 부가: saved_right_section_width에 이미 값이 있으면 잔존
        right_section_width는 덮어쓰지 않고 버려져야 한다(정본 값 보호).

        Logic:
            - version 1.1, ui.saved_right_section_width=700과
              ui.right_section_width=651이 공존하는 파일 작성
            - 마이그레이션 후 saved_right_section_width는 700 그대로 유지,
              right_section_width는 삭제됨을 확인
        """
        SettingsManager._instance = None

        resource_path = ResourcePath(tmp_path)
        resource_path.config_dir.mkdir(parents=True)

        old_settings = {
            "version": "1.1",
            "settings": {"theme": "dark", "language": "ko"},
            "ui": {"saved_right_section_width": 700, "right_section_width": 651}
        }
        with open(resource_path.settings_file, 'w', encoding='utf-8') as f:
            json.dump(old_settings, f)

        try:
            manager = SettingsManager(resource_path)

            ui = manager.get("ui")
            assert ui.get("saved_right_section_width") == 700
            assert "right_section_width" not in ui
            assert manager.get("version") == "1.3"
        finally:
            SettingsManager._instance = None

    def test_schema_rejects_invalid_theme_value(self, tmp_path):
        """
        S-027 DoD: 스키마가 실사용 키(settings.theme)의 잘못된 값(enum 외)을
        실제로 거부하는지 검증한다.

        Logic:
            - version 1.1, settings.theme="not_a_theme"인 파일 작성
            - SettingsManager 초기화 시 스키마 검증 실패 -> Fallback 사용
            - config_was_reset=True, reset_reason에 검증 실패 문구가 포함되는지 확인
        """
        from common.defaults import create_fallback_settings

        SettingsManager._instance = None

        resource_path = ResourcePath(tmp_path)
        resource_path.config_dir.mkdir(parents=True)

        bad_settings = create_fallback_settings()
        bad_settings["version"] = "1.1"
        bad_settings["settings"] = {"theme": "not_a_theme", "language": "ko"}
        with open(resource_path.settings_file, 'w', encoding='utf-8') as f:
            json.dump(bad_settings, f)

        try:
            manager = SettingsManager(resource_path)

            assert manager.config_was_reset is True
            assert "Validation failed" in manager.reset_reason
        finally:
            SettingsManager._instance = None
