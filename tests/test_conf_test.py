"""
Pytest 설정 및 공용 Fixture 정의 모듈

테스트 전반에서 사용되는 Mock 객체와 Fixture를 정의하여
중복 코드를 줄이고 테스트 일관성을 확보합니다.
"""
import sys
import os
import pytest
from unittest.mock import MagicMock
from PyQt5.QtWidgets import QApplication

# 프로젝트 루트 경로 설정
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.resource_path import ResourcePath
from view.main_window import MainWindow
from core.settings_manager import SettingsManager
from view.managers.theme_manager import ThemeManager
from view.managers.language_manager import LanguageManager
from view.managers.color_manager import ColorManager

@pytest.fixture(scope="session")
def qapp():
    """
    QApplication Session Fixture
    """
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app

@pytest.fixture
def resource_path():
    """ResourcePath Fixture"""
    return ResourcePath()

@pytest.fixture(autouse=True)
def init_managers(resource_path):
    """
    모든 테스트 전에 Manager들을 초기화합니다.
    MainPresenter나 MainWindow가 생성될 때 이 Manager들이 필요합니다.
    """
    SettingsManager(resource_path)
    ThemeManager(resource_path)
    LanguageManager(resource_path)
    ColorManager(resource_path)

@pytest.fixture
def mock_transport():
    """
    DeviceTransport Mock Fixture

    하드웨어 연결 없이 동작을 테스트하기 위한 Mock 객체입니다.
    기본적으로 '연결 성공' 상태를 시뮬레이션합니다.
    """
    transport = MagicMock()
    transport.open.return_value = True
    transport.is_open.return_value = True
    transport.read.return_value = b""
    transport.in_waiting = 0
    return transport

@pytest.fixture
def mock_connection_controller():
    """
    ConnectionController Mock Fixture

    View나 Presenter 테스트 시 Model 의존성을 끊기 위해 사용합니다.
    """
    controller = MagicMock()
    controller.has_active_connection = True
    controller.is_connection_open.return_value = True
    return controller

@pytest.fixture
def main_window(qapp, resource_path):
    """
    MainWindow Fixture

    GUI 테스트를 위한 메인 윈도우 인스턴스를 제공합니다.
    Manager들은 main.py 또는 별도 초기화 로직에 의해 설정되어야 함을 가정합니다.
    """
    window = MainWindow()
    return window
