"""
Pytest 설정 및 공통 Fixture 모듈

테스트 실행 시 전역적으로 사용되는 설정과 Fixture를 정의합니다.

## WHY
* 반복되는 테스트 객체(DTO, Mock) 생성 코드 제거
* 실제 하드웨어/파일시스템 의존성 격리
* PyQt5 QApplication 인스턴스의 전역 관리

## WHAT
* sys.path 설정
* QApplication instance 관리
* Serial/Settings test fixture
* 공통 DTO fixture

## HOW
* pytest.fixture 활용
* unittest.mock으로 hardware dependency 대체
* mutable global UI manager state는 snapshot/restore

pytest tests/test_conf_test.py -v
"""

import copy
import os
import sys
from unittest.mock import patch

import pytest

# -----------------------------------------------------------------------------
# 1. Path Setup
# -----------------------------------------------------------------------------
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PyQt5.QtWidgets import QApplication

from common.dtos import MacroEntry, ManualCommand, PortConfig
from common.enums import SerialFlowControl, SerialParity, SerialStopBits
from core.resource_path import ResourcePath


# -----------------------------------------------------------------------------
# 2. PyQt Fixtures
# -----------------------------------------------------------------------------

@pytest.fixture(scope="session")
def qapp():
    """테스트 session 전체에서 공유되는 QApplication instance를 제공한다."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


# -----------------------------------------------------------------------------
# 3. Core / Hardware Fixtures
# -----------------------------------------------------------------------------

@pytest.fixture
def mock_serial_port():
    """실제 hardware 없이 pyserial Serial 동작을 대체한다."""
    with patch("core.transport.serial_transport.serial.Serial") as mock_cls:
        mock_instance = mock_cls.return_value
        mock_instance.is_open = True
        mock_instance.in_waiting = 0

        def open_side_effect():
            mock_instance.is_open = True

        def close_side_effect():
            mock_instance.is_open = False

        mock_instance.open.side_effect = open_side_effect
        mock_instance.close.side_effect = close_side_effect
        mock_instance.write.side_effect = lambda data: len(data)

        yield mock_instance


@pytest.fixture
def mock_settings_manager(tmp_path):
    """tmp_path에 격리된 독립 SettingsManager instance를 제공한다.

    SettingsManager는 더 이상 Singleton이 아니므로 reset/recreate 절차가 필요 없다.
    fixture마다 ResourcePath와 instance를 새로 만들어 filesystem/state를 자연스럽게
    격리한다.
    """
    from core.settings_manager import SettingsManager

    resource_path = ResourcePath(tmp_path)
    resource_path.config_dir.mkdir(parents=True)
    yield SettingsManager(resource_path)


@pytest.fixture(autouse=True)
def stub_serial_port_enumeration(monkeypatch):
    """시스템 실제 Serial port 열거를 차단한다 (S-069).

    ## WHY
    `PortScanWorker.run()`의 `serial.tools.list_ports.comports()`는 Windows에서 ctypes로
    SetupAPI를 호출하는 실제 hardware enumeration이다. 워커 thread에서 이를 반복한
    과거 test에서 native abort가 관찰되어 deterministic unit/integration test 범위를
    넘어섰다.

    ## HOW
    기본적으로 빈 목록을 반환한다. LOOPBACK은 worker가 별도로 추가하므로 관련 test는
    유지된다. 특정 port list가 필요한 test는 이 autouse fixture 위에 다시 monkeypatch한다.
    """
    import serial.tools.list_ports

    monkeypatch.setattr(serial.tools.list_ports, "comports", lambda: [])


@pytest.fixture(autouse=True)
def reset_ui_manager_state():
    """공유 UI manager mutable state를 test 전후 snapshot/restore한다 (S-048).

    ## WHY
    ThemeManager/ColorManager/LanguageManager는 module-level shared instance를 여러 consumer가
    직접 import한다. class singleton field를 지웠다가 재생성하는 방식은 이미 배포된
    reference를 교체하지 못하므로 state isolation 방법으로 적합하지 않다.

    SettingsManager는 현재 fixture/runtime에서 명시적으로 생성·주입하는 일반 instance라
    이 global-state snapshot 대상에 포함되지 않는다.

    ## WHAT
    - ThemeManager current theme
    - ColorManager rules 및 COLOR_* palette
    - LanguageManager current language/resources

    nested mutable object가 있으므로 필요한 항목은 deepcopy한다.
    """
    from view.managers.color_manager import color_manager
    from view.managers.language_manager import language_manager
    from view.managers.theme_manager import theme_manager

    theme_snapshot = theme_manager._current_theme

    color_rules_snapshot = copy.deepcopy(color_manager._rules)
    color_palette_snapshot = {
        key: value
        for key, value in vars(color_manager).items()
        if key.startswith("COLOR_")
    }

    lang_current_snapshot = language_manager._current_language
    lang_resources_snapshot = copy.deepcopy(language_manager.resources)

    yield

    theme_manager._current_theme = theme_snapshot

    color_manager._rules = color_rules_snapshot
    for key, value in color_palette_snapshot.items():
        setattr(color_manager, key, value)

    language_manager._current_language = lang_current_snapshot
    language_manager.resources = lang_resources_snapshot


# -----------------------------------------------------------------------------
# 4. DTO Fixtures
# -----------------------------------------------------------------------------

@pytest.fixture
def sample_port_config():
    """테스트용 기본 PortConfig DTO를 반환한다."""
    return PortConfig(
        port="COM_TEST",
        baudrate=115200,
        bytesize=8,
        parity=SerialParity.NONE.value,
        stopbits=SerialStopBits.ONE.value,
        flowctrl=SerialFlowControl.NONE.value,
    )


@pytest.fixture
def sample_manual_command():
    """테스트용 ManualCommand DTO를 반환한다."""
    return ManualCommand(
        command="TEST_CMD",
        hex_mode=False,
        prefix_enabled=False,
        suffix_enabled=True,
        local_echo_enabled=True,
        broadcast_enabled=False,
    )


@pytest.fixture
def sample_macro_entry():
    """테스트용 MacroEntry DTO를 반환한다."""
    return MacroEntry(
        enabled=True,
        command="MACRO_CMD",
        delay_ms=100,
        hex_mode=False,
    )
