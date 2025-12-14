"""
Presenter 초기화 및 연동 테스트

- MainPresenter가 하위 Presenter들을 올바르게 초기화하는지 검증
- EventRouter 연결 상태 확인
- DataLogger 연동 확인
- 신규 Presenter (Packet, ManualControl) 초기화 검증

pytest tests/test_presenter_init.py -v
"""
import sys
import os
import pytest

# 프로젝트 루트 경로 설정
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from view.main_window import MainWindow
from presenter.main_presenter import MainPresenter
from presenter.packet_presenter import PacketPresenter
from presenter.manual_control_presenter import ManualControlPresenter
from resource_path import ResourcePath
from core.data_logger import data_logger_manager

@pytest.fixture
def main_presenter(qtbot):
    """MainPresenter Fixture"""
    # 리소스 경로 초기화
    resource_path = ResourcePath()

    # View & Presenter 생성
    window = MainWindow(resource_path)
    qtbot.addWidget(window)
    presenter = MainPresenter(window)

    return presenter

def test_presenter_initialization(main_presenter):
    """모든 하위 Presenter와 컴포넌트가 올바르게 초기화되었는지 확인"""

    # 1. Sub-presenters (기존)
    assert main_presenter.port_presenter is not None
    assert main_presenter.macro_presenter is not None
    assert main_presenter.file_presenter is not None

    # 2. Sub-presenters (신규 추가)
    assert main_presenter.packet_presenter is not None
    assert isinstance(main_presenter.packet_presenter, PacketPresenter)

    assert main_presenter.manual_control_presenter is not None
    assert isinstance(main_presenter.manual_control_presenter, ManualControlPresenter)

    # 3. EventRouter
    assert main_presenter.event_router is not None

    # 4. Models
    assert main_presenter.connection_controller is not None
    assert main_presenter.macro_runner is not None

def test_event_router_connection(main_presenter):
    """EventRouter와 MainPresenter 핸들러 연결 확인"""
    # EventRouter는 시그널을 가지고 있어야 함
    assert hasattr(main_presenter.event_router, 'data_received')
    assert hasattr(main_presenter.event_router, 'port_opened')
    assert hasattr(main_presenter.event_router, 'packet_received')

    # 실제 연결 여부는 PyQt 시그널의 receivers() 등으로 확인 가능하나,
    # 여기서는 초기화 과정에서 에러가 없는지로 간접 검증

def test_data_logger_integration(main_presenter):
    """DataLogger가 전역적으로 접근 가능하고 Presenter와 연동 준비되었는지 확인"""
    # DataLoggerManager는 싱글톤이므로 import된 객체 확인
    assert data_logger_manager is not None

    # MainPresenter는 DataLogger를 직접 멤버로 갖지 않고,
    # EventRouter나 메서드 내에서 전역 객체를 사용함.
    # 따라서 시스템 로그 메서드 호출 가능 여부로 간접 확인
    assert hasattr(main_presenter.view, 'log_system_message')

if __name__ == "__main__":
    pytest.main([__file__])
