"""
통합 테스트: 리팩토링된 구조 검증

- PortScanWorker 모델 계층 이동 검증
- PacketPresenter의 DI(Dependency Injection) 검증
- conftest.py의 공용 Fixture 활용 확인

pytest tests/test_integration_refactored.py -v
"""
import sys
import os
import pytest
from unittest.mock import MagicMock

# 프로젝트 루트 설정
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from model.port_scanner import PortScanWorker
from presenter.packet_presenter import PacketPresenter
from core.settings_manager import SettingsManager

def test_port_scan_worker_location():
    """PortScanWorker가 model 계층에 존재하는지 확인"""
    # import가 성공했으면 model에 존재하는 것임
    assert PortScanWorker.__module__ == "model.port_scanner"

    worker = PortScanWorker()
    assert hasattr(worker, 'ports_found')
    assert hasattr(worker, 'run')

def test_packet_presenter_di(mock_connection_controller, qapp):
    """PacketPresenter가 SettingsManager를 주입받는지 테스트"""
    # Mock Objects
    view_mock = MagicMock()
    event_router_mock = MagicMock()
    settings_mock = MagicMock() # Mock SettingsManager

    # DI 주입
    presenter = PacketPresenter(view_mock, event_router_mock, settings_mock)

    # 주입된 인스턴스를 사용하는지 확인
    assert presenter.settings_manager == settings_mock

    # apply_settings 호출 시 mock이 호출되어야 함
    presenter.apply_settings()
    settings_mock.get.assert_called()

def test_conftest_fixtures(qapp, resource_path, mock_transport):
    """conftest.py의 Fixture들이 정상 동작하는지 간단 검증"""
    assert qapp is not None
    assert resource_path.base_dir.exists()
    assert mock_transport.is_open() is True

if __name__ == "__main__":
    pytest.main([__file__])