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
from constants import ConfigKeys

@pytest.fixture
def mock_components():
    """테스트용 Mock 객체 생성"""
    view = MagicMock()
    connection_controller = MagicMock()
    local_echo_callback = MagicMock()
    return view, connection_controller, local_echo_callback

@pytest.fixture
def presenter(mock_components):
    """Presenter 인스턴스 생성"""
    view, connection_controller, local_echo_callback = mock_components
    # SettingsManager는 싱글톤이므로 설정 주입이 필요함 (여기서는 기본값 사용 가정)
    return ManualControlPresenter(view, connection_controller, local_echo_callback)

def test_send_text_with_prefix_suffix(presenter, mock_components):
    """텍스트 모드 전송 시 Prefix/Suffix 적용 테스트"""
    view, connection_controller, _ = mock_components

    # 설정 Mocking (SettingsManager 내부 동작에 의존하므로 값을 강제 설정)
    presenter.settings_manager.set(ConfigKeys.COMMAND_PREFIX, "start_")
    presenter.settings_manager.set(ConfigKeys.COMMAND_SUFFIX, "_end")

    # 포트 열림 상태
    connection_controller.has_active_connection = True

    # 전송 요청 (Prefix=True, Suffix=True)
    presenter.on_command_send_requested(
        text="command",
        hex_mode=False,
        command_prefix=True,
        command_suffix=True,
        local_echo=False
    )

    # 검증: "start_command_end"가 인코딩되어 전송되었는지
    expected_data = b"start_command_end"
    connection_controller.send_data.assert_called_once_with(expected_data)

def test_send_hex_mode(presenter, mock_components):
    """Hex 모드 전송 및 공백 처리 테스트"""
    _, connection_controller, _ = mock_components
    connection_controller.has_active_connection = True

    # 전송 요청 ("A1 B2" -> b'\xA1\xB2')
    presenter.on_command_send_requested(
        text="A1 B2",
        hex_mode=True,
        command_prefix=False,
        command_suffix=False,
        local_echo=False
    )

    expected_data = b"\xA1\xB2"
    connection_controller.send_data.assert_called_once_with(expected_data)

def test_send_blocked_when_port_closed(presenter, mock_components):
    """포트가 닫혀있을 때 전송 차단 테스트"""
    _, connection_controller, _ = mock_components
    connection_controller.has_active_connection = False  # 포트 닫힘

    presenter.on_command_send_requested("test", False, False, False, False)

    # 전송 메서드가 호출되지 않아야 함
    connection_controller.send_data.assert_not_called()

def test_local_echo_callback(presenter, mock_components):
    """Local Echo 콜백 호출 테스트"""
    _, connection_controller, local_echo_callback = mock_components
    connection_controller.has_active_connection = True

    presenter.on_command_send_requested(
        text="echo",
        hex_mode=False,
        command_prefix=False,
        command_suffix=False,
        local_echo=True  # 활성화
    )

    expected_data = b"echo"
    local_echo_callback.assert_called_once_with(expected_data)

if __name__ == "__main__":
    pytest.main([__file__])
