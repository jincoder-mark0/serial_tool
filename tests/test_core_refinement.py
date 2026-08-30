"""
코어 로직 정밀 테스트 모듈

애플리케이션의 기반이 되는 Core 유틸리티 및 매니저 클래스를 검증합니다.

## WHY
* 데이터 변환(CommandProcessor) 오류는 통신 전체의 신뢰성을 떨어뜨림
* 설정 관리(SettingsManager) 오류는 앱 초기화 실패의 원인이 됨

## WHAT
* CommandProcessor: ASCII/HEX 변환, 접두사/접미사 처리, 에러 핸들링
* SettingsManager: 싱글톤 패턴, 설정값 읽기/쓰기 무결성

## HOW
* 다양한 입력 케이스(정상/비정상)를 통한 CommandProcessor 검증
* pytest의 tmp_path와 patch를 활용한 설정 파일 I/O 격리 테스트

pytest tests/test_core_refinement.py -v
"""
import json
import sys
from pathlib import Path

import pytest
from unittest.mock import patch

from core.command_processor import CommandProcessor
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
        cmd = "Hello World"
        result = CommandProcessor.process_command(cmd, hex_mode=False)
        assert result == b"Hello World"

    def test_process_hex_command_valid(self):
        """유효한 HEX 문자열 변환 테스트."""
        cmd = "AA bb 01"
        result = CommandProcessor.process_command(cmd, hex_mode=True)
        assert result == b'\xaa\xbb\x01'

    def test_process_hex_command_invalid(self):
        """유효하지 않은 HEX 문자열 처리 테스트."""
        cmd = "ZZ Top"
        with pytest.raises(ValueError):
            CommandProcessor.process_command(cmd, hex_mode=True)

    def test_process_with_prefix_suffix(self):
        """접두사(Prefix) 및 접미사(Suffix) 결합 테스트."""
        result = CommandProcessor.process_command(
            "DATA",
            hex_mode=False,
            prefix="<STX>",
            suffix="<ETX>",
        )
        assert result == b"<STX>DATA<ETX>"

    def test_process_hex_with_prefix_suffix(self):
        """HEX 모드에서의 접두사/접미사 결합 테스트."""
        result = CommandProcessor.process_command(
            "FF 00",
            hex_mode=True,
            prefix="41",
            suffix="42",
        )
        assert result == b'A\xff\x00B'


class TestSettingsManager:
    """
    설정 관리자(SettingsManager)의 저장소 로직을 검증합니다.
    """

    def test_singleton_behavior(self):
        """싱글톤 패턴 동작 검증."""
        SettingsManager._instance = None

        m1 = SettingsManager()
        m2 = SettingsManager()

        assert m1 is m2
        SettingsManager._instance = None

    def test_get_set_value(self):
        """설정값 읽기 및 쓰기 테스트 (메모리 상)."""
        SettingsManager._instance = None
        manager = SettingsManager()

        with patch.object(manager, 'load_settings'), \
             patch.object(manager, 'save_settings'):
            manager.set(ConfigKeys.PORT_BAUDRATE, 9600)
            assert manager.get(ConfigKeys.PORT_BAUDRATE) == 9600
            assert manager.get("NON_EXISTENT_KEY", "DEFAULT") == "DEFAULT"

    def test_save_triggers_file_io(self, tmp_path):
        """저장 시 파일 쓰기 동작 검증 (Mocking 없이 tmp_path 사용)."""
        test_file = tmp_path / "config.json"
        SettingsManager._instance = None

        resource_path = ResourcePath(tmp_path)
        resource_path.config_dir.mkdir(parents=True)
        resource_path.settings_file = test_file
        manager = SettingsManager(resource_path)

        manager.set("test_key", 12345)
        manager.save_settings()

        # S-043: 개발 모드에서도 사용자 파일이 배포 기본값(test_file)과 분리되므로
        # 실제 저장 대상은 manager.user_settings_path(settings.local.json)다.
        assert manager.user_settings_path.exists()

        with open(manager.user_settings_path, 'r') as f:
            data = json.load(f)
            assert data["test_key"] == 12345

    def test_dev_mode_user_settings_path_is_separate_local_file(self, tmp_path):
        """
        S-043 회귀 방지: 개발 모드도 사용자 파일을 settings.local.json으로 분리해
        config_path(배포 기본값)는 읽기 전용 소스로만 남아야 한다.
        """
        SettingsManager._instance = None

        resource_path = ResourcePath(tmp_path)
        resource_path.config_dir.mkdir(parents=True)
        manager = SettingsManager(resource_path)

        assert manager.config_path != manager.user_settings_path
        assert resource_path.user_settings_file != resource_path.settings_file
        assert resource_path.user_settings_file == resource_path.settings_file.parent / 'settings.local.json'
        assert not resource_path.settings_file.exists()
        assert resource_path.user_settings_file.exists()

        SettingsManager._instance = None

    def test_frozen_mode_user_config_dir_uses_appdata(self, tmp_path, monkeypatch):
        """번들 실행(sys.frozen=True) 시 user_config_dir가 APPDATA/SerialTool을 가리키는지 검증."""
        fake_appdata = tmp_path / "AppData" / "Roaming"
        monkeypatch.setattr(sys, 'frozen', True, raising=False)
        monkeypatch.setenv('APPDATA', str(fake_appdata))

        resource_path = ResourcePath(tmp_path)

        expected = fake_appdata / 'SerialTool'
        assert resource_path.user_config_dir == expected
        assert expected.exists()
        assert resource_path.user_settings_file == expected / 'settings.json'

    def test_frozen_mode_appdata_missing_falls_back_to_home(self, tmp_path, monkeypatch):
        """APPDATA가 없는 번들 환경에서 홈 디렉터리 하위 .serial_tool로 폴백하는지 검증."""
        monkeypatch.setattr(sys, 'frozen', True, raising=False)
        monkeypatch.delenv('APPDATA', raising=False)
        monkeypatch.setattr(Path, 'home', classmethod(lambda cls: tmp_path))

        resource_path = ResourcePath(tmp_path)

        expected = tmp_path / '.serial_tool'
        assert resource_path.user_config_dir == expected
        assert expected.exists()

    def test_frozen_mode_first_run_migrates_from_default_distribution(self, tmp_path, monkeypatch):
        """번들 모드 첫 실행 시 기본 배포본을 사용자 경로로 이관하는지 검증."""
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
        original_distribution_text = resource_path.settings_file.read_text(encoding='utf-8')

        assert not resource_path.user_settings_file.exists()

        SettingsManager._instance = None
        manager = SettingsManager(resource_path)

        try:
            assert manager.user_settings_path.exists()
            assert manager.get("distribution_marker") == "from_default_distribution"
            assert resource_path.settings_file.read_text(encoding='utf-8') == original_distribution_text
        finally:
            SettingsManager._instance = None

    def test_frozen_mode_second_run_prefers_user_file(self, tmp_path, monkeypatch):
        """번들 모드에서 사용자 설정 파일이 있으면 사용자 파일을 우선 로드하는지 검증."""
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
        """S-027: global/settings가 공존하면 settings.*를 정본으로 유지하는지 검증."""
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

            with open(manager.user_settings_path, 'r', encoding='utf-8') as f:
                saved = json.load(f)
            assert "global" not in saved
        finally:
            SettingsManager._instance = None

    def test_migration_global_only_moves_to_settings(self, tmp_path):
        """S-027: global만 있는 1.0 파일의 값을 settings.*로 이관하는지 검증."""
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
        """S-027: ui 블록의 죽은 폰트 키 4종이 마이그레이션 후 제거되는지 검증."""
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
        """S-030: 현재 버전 1.3 파일은 마이그레이션 없이 통과하는지 검증."""
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
        """S-030: 최상위 serial은 제거하되 ports.tabs의 flowctrl은 보존하는지 검증."""
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

            with open(manager.user_settings_path, 'r', encoding='utf-8') as f:
                saved = json.load(f)
            assert "serial" not in saved
            assert saved["ports"]["tabs"][0]["serial"]["flowctrl"] == "RTS/CTS"
        finally:
            SettingsManager._instance = None

    def test_defaults_have_no_orphan_serial_block(self):
        """S-030: create_fallback_settings()에 최상위 serial 블록이 없는지 검증."""
        from common.defaults import create_fallback_settings

        defaults = create_fallback_settings()
        assert "serial" not in defaults

    def test_migrate_settings_applied_to_defaults_is_noop(self):
        """S-030: 현재 기본 설정에 migration을 적용해도 no-op인지 검증."""
        from common.defaults import create_fallback_settings

        SettingsManager._instance = None
        manager = SettingsManager.__new__(SettingsManager)

        defaults = create_fallback_settings()

        assert manager._needs_migration(defaults) is False
        assert manager._migrate_settings(defaults) == defaults

    def test_migration_v1_0_saved_right_width_not_renamed(self, tmp_path):
        """S-028: 1.0의 saved_right_section_width가 그대로 보존되는지 검증."""
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
        """S-028: stale right_section_width를 정본 키로 병합한 뒤 제거하는지 검증."""
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
        """S-028: 정본 saved_right_section_width가 있으면 stale 값을 버리는지 검증."""
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
        """S-027: 스키마가 잘못된 theme enum 값을 거부하는지 검증."""
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
