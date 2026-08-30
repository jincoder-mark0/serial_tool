"""
코어 로직 정밀 테스트 모듈

애플리케이션의 기반이 되는 Core utility 및 manager class를 검증합니다.

## WHY
* 데이터 변환(CommandProcessor) 오류는 통신 전체의 신뢰성을 떨어뜨림
* 설정 관리(SettingsManager) 오류는 앱 초기화 실패의 원인이 됨

## WHAT
* CommandProcessor: ASCII/HEX 변환, 접두사/접미사 처리, error handling
* SettingsManager: 독립 instance, 설정값 읽기/쓰기, migration/복구 무결성

## HOW
* 다양한 정상/비정상 입력으로 CommandProcessor 검증
* pytest tmp_path로 SettingsManager file I/O를 instance별 격리

pytest tests/test_core_refinement.py -v
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from common.constants import ConfigKeys
from core.command_processor import CommandProcessor
from core.resource_path import ResourcePath
from core.settings_manager import SettingsManager


class TestCommandProcessor:
    """CommandProcessor 데이터 변환 로직 검증."""

    def test_process_ascii_command(self):
        cmd = "Hello World"
        result = CommandProcessor.process_command(cmd, hex_mode=False)
        assert result == b"Hello World"

    def test_process_hex_command_valid(self):
        cmd = "AA bb 01"
        result = CommandProcessor.process_command(cmd, hex_mode=True)
        assert result == b"\xaa\xbb\x01"

    def test_process_hex_command_invalid(self):
        cmd = "ZZ Top"
        with pytest.raises(ValueError):
            CommandProcessor.process_command(cmd, hex_mode=True)

    def test_process_with_prefix_suffix(self):
        result = CommandProcessor.process_command(
            "DATA",
            hex_mode=False,
            prefix="<STX>",
            suffix="<ETX>",
        )
        assert result == b"<STX>DATA<ETX>"

    def test_process_hex_with_prefix_suffix(self):
        result = CommandProcessor.process_command(
            "FF 00",
            hex_mode=True,
            prefix="41",
            suffix="42",
        )
        assert result == b"A\xff\x00B"


class TestSettingsManager:
    """SettingsManager instance/file/migration 동작 검증."""

    def test_instances_are_independent(self, tmp_path):
        """Singleton 제거 후 서로 다른 생성은 서로 다른 state를 소유해야 한다."""
        path_a = ResourcePath(tmp_path / "a")
        path_b = ResourcePath(tmp_path / "b")
        path_a.config_dir.mkdir(parents=True)
        path_b.config_dir.mkdir(parents=True)

        manager_a = SettingsManager(path_a)
        manager_b = SettingsManager(path_b)

        assert manager_a is not manager_b
        assert manager_a._resource_path is path_a
        assert manager_b._resource_path is path_b

        manager_a.set("instance_marker", "A")
        assert manager_a.get("instance_marker") == "A"
        assert manager_b.get("instance_marker") is None

    def test_get_set_value(self):
        """설정값 읽기/쓰기 및 missing default를 검증한다."""
        manager = SettingsManager()

        with patch.object(manager, "load_settings"), patch.object(
            manager,
            "save_settings",
        ):
            manager.set(ConfigKeys.PORT_BAUDRATE, 9600)
            assert manager.get(ConfigKeys.PORT_BAUDRATE) == 9600
            assert manager.get("NON_EXISTENT_KEY", "DEFAULT") == "DEFAULT"

    def test_save_triggers_file_io(self, tmp_path):
        """저장 시 사용자 설정 파일에 실제 write되는지 검증한다."""
        test_file = tmp_path / "config.json"
        resource_path = ResourcePath(tmp_path)
        resource_path.config_dir.mkdir(parents=True)
        resource_path.settings_file = test_file
        manager = SettingsManager(resource_path)

        manager.set("test_key", 12345)
        manager.save_settings()

        # 개발 모드에서도 사용자 파일은 settings.local.json으로 분리된다.
        assert manager.user_settings_path.exists()
        with open(manager.user_settings_path, "r") as file:
            data = json.load(file)
        assert data["test_key"] == 12345

    def test_dev_mode_user_settings_path_is_separate_local_file(self, tmp_path):
        """개발 모드 배포 기본값과 사용자 쓰기 파일을 분리한다."""
        resource_path = ResourcePath(tmp_path)
        resource_path.config_dir.mkdir(parents=True)
        manager = SettingsManager(resource_path)

        assert manager.config_path != manager.user_settings_path
        assert resource_path.user_settings_file != resource_path.settings_file
        assert (
            resource_path.user_settings_file
            == resource_path.settings_file.parent / "settings.local.json"
        )
        assert not resource_path.settings_file.exists()
        assert resource_path.user_settings_file.exists()

    def test_frozen_mode_user_config_dir_uses_appdata(self, tmp_path, monkeypatch):
        """번들 실행 시 user config dir가 APPDATA/SerialTool을 사용한다."""
        fake_appdata = tmp_path / "AppData" / "Roaming"
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setenv("APPDATA", str(fake_appdata))

        resource_path = ResourcePath(tmp_path)

        expected = fake_appdata / "SerialTool"
        assert resource_path.user_config_dir == expected
        assert expected.exists()
        assert resource_path.user_settings_file == expected / "settings.json"

    def test_frozen_mode_appdata_missing_falls_back_to_home(
        self,
        tmp_path,
        monkeypatch,
    ):
        """APPDATA가 없으면 home/.serial_tool로 fallback한다."""
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.delenv("APPDATA", raising=False)
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))

        resource_path = ResourcePath(tmp_path)

        expected = tmp_path / ".serial_tool"
        assert resource_path.user_config_dir == expected
        assert expected.exists()

    def test_frozen_mode_first_run_migrates_from_default_distribution(
        self,
        tmp_path,
        monkeypatch,
    ):
        """번들 첫 실행 시 배포 기본본을 사용자 경로로 이관한다."""
        from common.defaults import create_fallback_settings

        fake_appdata = tmp_path / "AppData"
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setenv("APPDATA", str(fake_appdata))

        resource_path = ResourcePath(tmp_path)
        resource_path.config_dir.mkdir(parents=True)

        default_distribution = create_fallback_settings()
        default_distribution["distribution_marker"] = "from_default_distribution"
        with open(resource_path.settings_file, "w", encoding="utf-8") as file:
            json.dump(default_distribution, file)
        original_distribution_text = resource_path.settings_file.read_text(
            encoding="utf-8"
        )

        assert not resource_path.user_settings_file.exists()

        manager = SettingsManager(resource_path)

        assert manager.user_settings_path.exists()
        assert manager.get("distribution_marker") == "from_default_distribution"
        assert (
            resource_path.settings_file.read_text(encoding="utf-8")
            == original_distribution_text
        )

    def test_frozen_mode_second_run_prefers_user_file(self, tmp_path, monkeypatch):
        """번들에서 사용자 파일이 존재하면 배포 기본본보다 우선한다."""
        from common.defaults import create_fallback_settings

        fake_appdata = tmp_path / "AppData"
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setenv("APPDATA", str(fake_appdata))

        resource_path = ResourcePath(tmp_path)
        resource_path.config_dir.mkdir(parents=True)

        default_distribution = create_fallback_settings()
        default_distribution["distribution_marker"] = "from_default_distribution"
        with open(resource_path.settings_file, "w", encoding="utf-8") as file:
            json.dump(default_distribution, file)

        user_settings = create_fallback_settings()
        user_settings["distribution_marker"] = "from_user_file"
        with open(resource_path.user_settings_file, "w", encoding="utf-8") as file:
            json.dump(user_settings, file)

        manager = SettingsManager(resource_path)
        assert manager.get("distribution_marker") == "from_user_file"

    def test_migration_global_and_settings_coexist_settings_wins(self, tmp_path):
        """global/settings가 공존하면 settings.* 값을 우선한다."""
        resource_path = ResourcePath(tmp_path)
        resource_path.config_dir.mkdir(parents=True)

        old_settings = {
            "version": "1.0",
            "global": {"theme": "dark", "language": "ko"},
            "settings": {"theme": "dracula", "language": "en"},
        }
        with open(resource_path.settings_file, "w", encoding="utf-8") as file:
            json.dump(old_settings, file)

        manager = SettingsManager(resource_path)

        assert manager.get("settings.theme") == "dracula"
        assert manager.get("settings.language") == "en"
        assert manager.get("global") is None
        assert manager.get("version") == "1.3"

        with open(manager.user_settings_path, "r", encoding="utf-8") as file:
            saved = json.load(file)
        assert "global" not in saved

    def test_migration_global_only_moves_to_settings(self, tmp_path):
        """global만 있는 1.0 값을 settings.*로 이관한다."""
        resource_path = ResourcePath(tmp_path)
        resource_path.config_dir.mkdir(parents=True)

        old_settings = {
            "version": "1.0",
            "global": {"theme": "light", "language": "ko"},
        }
        with open(resource_path.settings_file, "w", encoding="utf-8") as file:
            json.dump(old_settings, file)

        manager = SettingsManager(resource_path)

        assert manager.get("settings.theme") == "light"
        assert manager.get("settings.language") == "ko"
        assert manager.get("global") is None

    def test_migration_removes_dead_ui_font_keys(self, tmp_path):
        """과거 ui font key 4종을 migration 후 제거한다."""
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
                "fixed_font_size": 9,
            },
        }
        with open(resource_path.settings_file, "w", encoding="utf-8") as file:
            json.dump(old_settings, file)

        manager = SettingsManager(resource_path)
        ui = manager.get("ui")

        assert "proportional_font_family" not in ui
        assert "proportional_font_size" not in ui
        assert "fixed_font_family" not in ui
        assert "fixed_font_size" not in ui
        assert ui.get("max_log_lines") == 500

    def test_migration_v1_3_file_passes_unchanged(self, tmp_path):
        """현재 version 1.3 파일은 migration 없이 통과한다."""
        from common.defaults import create_fallback_settings

        resource_path = ResourcePath(tmp_path)
        resource_path.config_dir.mkdir(parents=True)

        current_settings = create_fallback_settings()
        current_settings["version"] = "1.3"
        current_settings["settings"] = {"theme": "dracula", "language": "en"}
        with open(resource_path.settings_file, "w", encoding="utf-8") as file:
            json.dump(current_settings, file)

        manager = SettingsManager(resource_path)

        assert manager._needs_migration({"version": "1.3"}) is False
        assert manager.get("settings.theme") == "dracula"
        assert manager.get("settings.language") == "en"
        assert manager.get("global") is None

    def test_migration_v1_2_removes_orphan_serial_keeps_tab_flowctrl(self, tmp_path):
        """최상위 serial은 제거하되 ports.tabs[*].serial은 보존한다."""
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
                "flow_control": "None",
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
                            "flowctrl": "RTS/CTS",
                        },
                    }
                ]
            },
        }
        with open(resource_path.settings_file, "w", encoding="utf-8") as file:
            json.dump(old_settings, file)

        manager = SettingsManager(resource_path)

        assert manager.get("serial") is None
        tabs = manager.get("ports.tabs")
        assert tabs[0]["serial"]["flowctrl"] == "RTS/CTS"
        assert manager.get("version") == "1.3"

        with open(manager.user_settings_path, "r", encoding="utf-8") as file:
            saved = json.load(file)
        assert "serial" not in saved
        assert saved["ports"]["tabs"][0]["serial"]["flowctrl"] == "RTS/CTS"

    def test_defaults_have_no_orphan_serial_block(self):
        """canonical fallback에 최상위 serial block이 없어야 한다."""
        from common.defaults import create_fallback_settings

        defaults = create_fallback_settings()
        assert "serial" not in defaults

    def test_migrate_settings_applied_to_defaults_is_noop(self):
        """현재 fallback에 migration을 적용해도 동일해야 한다."""
        from common.defaults import create_fallback_settings

        manager = object.__new__(SettingsManager)
        defaults = create_fallback_settings()

        assert manager._needs_migration(defaults) is False
        assert manager._migrate_settings(defaults) == defaults

    def test_migration_v1_0_saved_right_width_not_renamed(self, tmp_path):
        """1.0 saved_right_section_width는 그대로 보존한다."""
        resource_path = ResourcePath(tmp_path)
        resource_path.config_dir.mkdir(parents=True)

        old_settings = {
            "version": "1.0",
            "global": {"theme": "dark", "language": "ko"},
            "ui": {"saved_right_section_width": 598},
        }
        with open(resource_path.settings_file, "w", encoding="utf-8") as file:
            json.dump(old_settings, file)

        manager = SettingsManager(resource_path)
        ui = manager.get("ui")

        assert ui.get("saved_right_section_width") == 598
        assert "right_section_width" not in ui
        assert manager.get("version") == "1.3"

    def test_migration_v1_1_stale_right_width_merged_and_removed(self, tmp_path):
        """stale right_section_width를 canonical key로 이관한다."""
        resource_path = ResourcePath(tmp_path)
        resource_path.config_dir.mkdir(parents=True)

        old_settings = {
            "version": "1.1",
            "settings": {"theme": "dark", "language": "ko"},
            "ui": {"right_section_width": 651},
        }
        with open(resource_path.settings_file, "w", encoding="utf-8") as file:
            json.dump(old_settings, file)

        manager = SettingsManager(resource_path)
        ui = manager.get("ui")

        assert ui.get("saved_right_section_width") == 651
        assert "right_section_width" not in ui
        assert manager.get("version") == "1.3"

    def test_migration_v1_1_stale_right_width_discarded_when_saved_already_set(
        self,
        tmp_path,
    ):
        """canonical width가 있으면 stale width를 버린다."""
        resource_path = ResourcePath(tmp_path)
        resource_path.config_dir.mkdir(parents=True)

        old_settings = {
            "version": "1.1",
            "settings": {"theme": "dark", "language": "ko"},
            "ui": {"saved_right_section_width": 700, "right_section_width": 651},
        }
        with open(resource_path.settings_file, "w", encoding="utf-8") as file:
            json.dump(old_settings, file)

        manager = SettingsManager(resource_path)
        ui = manager.get("ui")

        assert ui.get("saved_right_section_width") == 700
        assert "right_section_width" not in ui
        assert manager.get("version") == "1.3"

    def test_schema_rejects_invalid_theme_value(self, tmp_path):
        """schema가 invalid theme enum을 거부하고 fallback으로 복구한다."""
        from common.defaults import create_fallback_settings

        resource_path = ResourcePath(tmp_path)
        resource_path.config_dir.mkdir(parents=True)

        bad_settings = create_fallback_settings()
        bad_settings["version"] = "1.1"
        bad_settings["settings"] = {"theme": "not_a_theme", "language": "ko"}
        with open(resource_path.settings_file, "w", encoding="utf-8") as file:
            json.dump(bad_settings, file)

        manager = SettingsManager(resource_path)

        assert manager.config_was_reset is True
        assert "Validation failed" in manager.reset_reason
