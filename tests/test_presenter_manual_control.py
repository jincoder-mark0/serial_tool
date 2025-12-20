"""
ManualControlPresenter 단위 테스트

수동 제어 로직(포맷팅, Hex 변환, 전송 제어)을 검증합니다.
"""
import sys
import os
import pytest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from presenter.manual_control_presenter import ManualControlPresenter
from core.settings_manager import SettingsManager
from common.constants import ConfigKeys
from common.dtos import ManualCommand

@pytest.fixture
def mock_components():
    """테스트용 Mock 객체 생성"""
    view = MagicMock()
    connection_controller = MagicMock()
    local_echo_callback = MagicMock()
    # 활성 포트 반환 Mock
    get_active_port = MagicMock(return_value="COM1")
    return view, connection_controller, local_echo_callback, get_active_port

@pytest.fixture
def presenter(mock_components):
    """Presenter 인스턴스 생성"""
    view, connection_controller, local_echo_callback, get_active_port = mock_components
    return ManualControlPresenter(view, connection_controller, local_echo_callback, get_active_port)

def test_send_text_with_prefix_suffix(presenter, mock_components):
    """텍스트 모드 전송 시 Prefix/Suffix 적용 테스트"""
    view, connection_controller, _, _ = mock_components

    # 설정 Mocking
    presenter.settings_manager.set(ConfigKeys.COMMAND_PREFIX, "start_")
    presenter.settings_manager.set(ConfigKeys.COMMAND_SUFFIX, "_end")

    # 포트 열림 상태
    connection_controller.has_active_connection = True

    # DTO 생성
    manual_command = ManualCommand(
        command="command",
        hex_mode=False,
        prefix_enabled=True,
        suffix_enabled=True,
        local_echo_enabled=False
    )

    # 전송 요청
    presenter.on_send_requested(manual_command)

    # 검증: "start_command_end"가 인코딩되어 전송되었는지
    expected_data = b"start_command_end"
    connection_controller.send_data.assert_called_once_with("COM1", expected_data)

def test_send_hex_mode(presenter, mock_components):
    """Hex 모드 전송 및 공백 처리 테스트"""
    _, connection_controller, _, _ = mock_components
    connection_controller.has_active_connection = True

    # DTO 생성 ("A1 B2" -> b'\xA1\xB2')
    manual_command = ManualCommand(
        command="A1 B2",
        hex_mode=True
    )

    presenter.on_send_requested(manual_command)

    expected_data = b"\xA1\xB2"
    connection_controller.send_data.assert_called_once_with("COM1", expected_data)

def test_send_blocked_when_port_closed(presenter, mock_components):
    """포트가 닫혀있을 때 전송 차단 테스트"""
    _, connection_controller, _, _ = mock_components
    connection_controller.has_active_connection = False  # 포트 닫힘

    manual_command = ManualCommand(command="test")
    presenter.on_send_requested(manual_command)

    # 전송 메서드가 호출되지 않아야 함
    connection_controller.send_data.assert_not_called()

def test_local_echo_callback(presenter, mock_components):
    """Local Echo 콜백 호출 테스트"""
    _, connection_controller, local_echo_callback, _ = mock_components
    connection_controller.has_active_connection = True

    manual_command = ManualCommand(
        command="echo",
        local_echo_enabled=True
    )

    presenter.on_send_requested(manual_command)

    expected_data = b"echo"
    local_echo_callback.assert_called_once_with(expected_data)

if __name__ == "__main__":
    pytest.main([__file__])
