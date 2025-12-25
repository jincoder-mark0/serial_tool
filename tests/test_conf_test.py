"""
Pytest 설정 및 공통 Fixture 모듈

테스트 실행 시 전역적으로 사용되는 설정과 Fixture를 정의합니다.

## WHY
* 반복되는 테스트 객체(DTO, Mock) 생성 코드 제거
* 실제 하드웨어/파일시스템 의존성 격리 (Mocking)
* PyQt5 QApplication 인스턴스의 전역 관리

## WHAT
* sys.path 설정 (프로젝트 루트 인식)
* QApplication 인스턴스 관리 (qapp)
* Serial/Settings/EventBus Mocking Fixture
* 공통 DTO 데이터 Fixture

## HOW
* pytest.fixture 데코레이터 활용
* unittest.mock.MagicMock을 이용한 가짜 객체 주입
* autouse=True를 통한 자동 초기화

pytest tests/test_conf_test.py -v
"""
import sys
import os
import pytest
from unittest.mock import MagicMock, patch

# -----------------------------------------------------------------------------
# 1. 경로 설정 (Path Setup)
# -----------------------------------------------------------------------------
# 프로젝트 루트 디렉토리를 sys.path에 추가하여 모듈 import 에러 방지
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from PyQt5.QtWidgets import QApplication
from common.dtos import PortConfig, ManualCommand, MacroEntry
from common.enums import SerialParity, SerialStopBits, SerialFlowControl
from core.event_bus import event_bus


# -----------------------------------------------------------------------------
# 2. PyQt 관련 Fixture (PyQt Fixtures)
# -----------------------------------------------------------------------------

@pytest.fixture(scope="session")
def qapp():
    """
    테스트 세션 전체에서 공유되는 QApplication 인스턴스를 제공합니다.

    PyQt 위젯을 테스트하려면 반드시 하나의 QApplication 인스턴스가 필요합니다.
    이미 생성된 인스턴스가 있다면 그것을 반환하고, 없다면 새로 생성합니다.

    Yields:
        QApplication: Qt 애플리케이션 인스턴스.
    """
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app
    # 세션 종료 시 별도 정리 작업은 필요 없음 (프로세스 종료로 처리)


# -----------------------------------------------------------------------------
# 3. Mocking Fixtures (Core & Hardware)
# -----------------------------------------------------------------------------

@pytest.fixture
def mock_serial_port():
    """
    pyserial의 Serial 클래스를 Mocking합니다.

    실제 하드웨어 연결 없이 시리얼 통신 로직을 테스트하기 위해 사용됩니다.
    read, write, open, close 등의 메서드가 Mock 객체로 대체됩니다.

    Yields:
        MagicMock: Mocking된 Serial 인스턴스.
    """
    with patch("core.transport.serial_transport.serial.Serial") as mock_cls:
        mock_instance = mock_cls.return_value

        # 기본 동작 설정
        mock_instance.is_open = False

        # open() 호출 시 is_open을 True로 변경하는 사이드 이펙트
        def open_side_effect():
            mock_instance.is_open = True

        # close() 호출 시 is_open을 False로 변경하는 사이드 이펙트
        def close_side_effect():
            mock_instance.is_open = False

        mock_instance.open.side_effect = open_side_effect
        mock_instance.close.side_effect = close_side_effect

        # write()는 보낸 바이트 수를 반환하도록 설정
        mock_instance.write.side_effect = lambda data: len(data)

        yield mock_instance


@pytest.fixture
def mock_settings_manager(tmp_path):
    """
    SettingsManager를 Mocking하여 임시 경로를 사용하도록 설정합니다.

    실제 config.json 파일을 덮어쓰지 않고 테스트하기 위함입니다.
    pytest의 tmp_path 픽스처를 사용하여 격리된 파일 시스템을 제공합니다.

    Args:
        tmp_path (Path): pytest가 제공하는 임시 디렉토리 경로.

    Yields:
        SettingsManager: 임시 경로로 초기화된 설정 관리자.
    """
    # SettingsManager가 싱글톤일 경우를 대비해 초기화 로직을 우회하거나
    # 파일 경로를 패치해야 합니다. 여기서는 파일 경로를 패치한다고 가정합니다.
    config_path = tmp_path / "test_config.json"

    with patch("core.settings_manager.CONFIG_FILE_PATH", str(config_path)):
        from core.settings_manager import SettingsManager
        # 싱글톤 인스턴스 리셋 (테스트 격리)
        SettingsManager._instance = None
        manager = SettingsManager()
        yield manager
        # 테스트 후 정리
        SettingsManager._instance = None


@pytest.fixture(autouse=True)
def reset_event_bus():
    """
    각 테스트 실행 전후에 EventBus를 초기화합니다 (자동 적용).

    테스트 간 이벤트 구독(Subscribe) 상태가 공유되어 발생하는 사이드 이펙트를 방지합니다.
    """
    # 테스트 전: 구독자 목록 초기화
    # (EventBus 내부 구현에 따라 _subscribers 접근이 필요할 수 있음)
    if hasattr(event_bus, '_subscribers'):
        event_bus._subscribers.clear()

    yield

    # 테스트 후: 다시 초기화
    if hasattr(event_bus, '_subscribers'):
        event_bus._subscribers.clear()


# -----------------------------------------------------------------------------
# 4. Data Object Fixtures (DTOs)
# -----------------------------------------------------------------------------

@pytest.fixture
def sample_port_config():
    """
    테스트용 기본 PortConfig DTO를 제공합니다.

    Returns:
        PortConfig: 유효한 값을 가진 포트 설정 객체.
    """
    return PortConfig(
        port="COM_TEST",
        baudrate=115200,
        bytesize=8,
        parity=SerialParity.NONE.value,
        stopbits=SerialStopBits.ONE.value,
        flowctrl=SerialFlowControl.NONE.value
    )


@pytest.fixture
def sample_manual_command():
    """
    테스트용 기본 ManualCommand DTO를 제공합니다.

    Returns:
        ManualCommand: "TEST_CMD" 명령어를 가진 객체.
    """
    return ManualCommand(
        command="TEST_CMD",
        hex_mode=False,
        prefix_enabled=False,
        suffix_enabled=True,  # 보통 \n을 붙이므로 True로 설정
        local_echo_enabled=True,
        broadcast_enabled=False
    )


@pytest.fixture
def sample_macro_entry():
    """
    테스트용 기본 MacroEntry DTO를 제공합니다.

    Returns:
        MacroEntry: 매크로 실행 테스트용 객체.
    """
    return MacroEntry(
        enabled=True,
        command="MACRO_CMD",
        delay_ms=100,
        hex_mode=False
    )