"""
PacketPresenter 단위 테스트

패킷 데이터 포맷팅 및 View 업데이트 로직을 검증합니다.
"""
import sys
import os
import pytest
from unittest.mock import MagicMock
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from presenter.packet_presenter import PacketPresenter
from constants import ConfigKeys

# Packet Mock (model.packet_parser.Packet과 동일 구조)
@dataclass
class MockPacket:
    data: bytes
    timestamp: float
    metadata: dict = None

@pytest.fixture
def mock_components():
    view = MagicMock()
    event_router = MagicMock()
    return view, event_router

@pytest.fixture
def presenter(mock_components):
    view, event_router = mock_components
    return PacketPresenter(view, event_router)

def test_apply_settings(presenter, mock_components):
    """설정값이 View에 올바르게 적용되는지 테스트"""
    view, _ = mock_components

    # 설정값 강제 주입
    presenter.settings_manager.set(ConfigKeys.INSPECTOR_BUFFER_SIZE, 500)
    presenter.settings_manager.set(ConfigKeys.INSPECTOR_AUTOSCROLL, False)

    presenter.apply_settings()

    view.set_inspector_options.assert_called_with(500, False)

def test_packet_formatting(presenter, mock_components):
    """패킷 데이터(Hex/ASCII/Time) 포맷팅 테스트"""
    view, _ = mock_components

    # 1. 테스트 패킷 생성 (ABC -> 41 42 43)
    packet = MockPacket(
        data=b"ABC",
        timestamp=1700000000.123, # 고정 시간
        metadata={"type": "TEST"}
    )

    # 2. 이벤트 핸들러 호출
    presenter.on_packet_received("COM1", packet)

    # 3. View 호출 검증
    # 인자: time_str, packet_type, data_hex, data_ascii
    args = view.add_packet_to_view.call_args[0]

    # 시간 포맷 확인 (로컬 타임존에 따라 시간은 다를 수 있으나 포맷은 확인 가능)
    assert args[0].endswith(".123") # 밀리초 확인
    assert args[1] == "TEST"        # 타입 확인
    assert args[2] == "41 42 43"    # HEX 확인
    assert args[3] == "ABC"         # ASCII 확인

def test_control_character_handling(presenter, mock_components):
    """제어 문자(0x00 등)가 '.'으로 치환되는지 테스트"""
    view, _ = mock_components

    # Null byte 포함 패킷
    packet = MockPacket(data=b"A\x00B", timestamp=0, metadata={})

    presenter.on_packet_received("COM1", packet)

    args = view.add_packet_to_view.call_args[0]
    assert args[2] == "41 00 42" # Hex
    assert args[3] == "A.B"      # ASCII (0x00 -> .)

if __name__ == "__main__":
    pytest.main([__file__])
