"""
메인 프레젠터 초기화 테스트 모듈

MainPresenter의 객체 생성 및 초기화 시퀀스가 올바르게 수행되는지 검증합니다.

## WHY
* 애플리케이션의 진입점(Entry Point)이므로 초기화 실패 시 앱 구동 불가
* 하위 Presenter, Controller, EventRouter 간의 연결(Wiring) 무결성 확인
* LifecycleManager를 통한 초기화 로직 위임이 정상적으로 일어나는지 검증

## WHAT
* MainPresenter 인스턴스 생성 테스트
* 하위 컴포넌트(Port/Macro/File Presenter, Controller) 생성 확인
* View의 주요 UI 요소 접근 및 시그널 연결 확인
* LifecycleManager.initialize_app 호출 여부 검증

## HOW
* 복잡한 MainWindow 구조를 MagicMock으로 모방하여 GUI 의존성 제거
* unittest.mock.patch를 사용하여 LifecycleManager의 실행 가로채기

pytest tests/test_presenter_init.py -v
"""
import pytest
from unittest.mock import MagicMock, patch

from presenter.main_presenter import MainPresenter


@pytest.fixture
def mock_main_window():
    """
    MainPresenter 초기화를 위한 가짜 MainWindow 객체를 생성합니다.

    MainPresenter는 생성 시점에 View의 여러 하위 위젯(Left/Right Section, Panels)에
    접근하므로, 해당 구조를 모방한 Mock 객체가 필요합니다.

    Returns:
        MagicMock: 구성된 가짜 MainWindow 객체.
    """
    view = MagicMock()

    # 1. 메인 섹션 구조 Mocking
    view.left_section = MagicMock()
    view.right_section = MagicMock()

    # 2. 하위 패널 Mocking
    # Port Tab Panel
    view.left_section.port_tab_panel = MagicMock()
    view.left_section.port_tab_panel.currentIndex.return_value = 0
    view.left_section.port_tab_panel.widget.return_value = MagicMock()  # PortPanel

    # Manual Control Panel
    view.left_section.manual_control_panel = MagicMock()

    # System Log Widget
    view.left_section.system_log_widget = MagicMock()

    # Packet Panel
    view.right_section.packet_panel = MagicMock()

    # Macro Views
    view.macro_view = MagicMock()
    view.port_view = MagicMock()

    # 3. 주요 시그널 Mocking
    view.settings_save_requested = MagicMock()
    view.font_settings_changed = MagicMock()
    view.close_requested = MagicMock()
    view.preferences_requested = MagicMock()
    view.shortcut_connect_requested = MagicMock()
    view.shortcut_disconnect_requested = MagicMock()
    view.shortcut_clear_requested = MagicMock()
    view.file_transfer_dialog_opened = MagicMock()
    view.port_tab_added = MagicMock()

    # 4. 주요 메서드 반환값 설정
    view.get_port_tabs_count.return_value = 0

    return view


class TestMainPresenterInit:
    """
    MainPresenter의 초기화 및 구성 요소를 검증하는 테스트 클래스
    """

    def test_component_creation(self, mock_main_window, mock_settings_manager):
        """
        하위 Presenter 및 핵심 모듈 생성 테스트

        Logic:
            - MainPresenter 생성
            - 내부 속성(presenter, controller 등)이 None이 아닌지 확인
        """
        # GIVEN: SettingsManager Mocking (싱글톤 초기화 방지 및 파일 I/O 방지)
        with patch('presenter.main_presenter.SettingsManager', return_value=mock_settings_manager):
            # WHEN: Presenter 생성
            presenter = MainPresenter(mock_main_window)

            # THEN: 핵심 모델 생성 확인
            assert presenter.connection_controller is not None
            assert presenter.macro_runner is not None
            assert presenter.event_router is not None
            assert presenter.data_handler is not None

            # THEN: 하위 Presenter 생성 확인
            assert presenter.port_presenter is not None
            assert presenter.macro_presenter is not None
            assert presenter.file_presenter is not None
            assert presenter.packet_presenter is not None
            assert presenter.manual_control_presenter is not None

            # THEN: LifecycleManager 생성 확인
            assert presenter.lifecycle_manager is not None

    def test_lifecycle_delegation(self, mock_main_window, mock_settings_manager):
        """
        초기화 로직 위임(Delegation) 테스트

        Logic:
            - AppLifecycleManager를 patch하여 감시
            - MainPresenter 생성 시 initialize_app() 메서드가 호출되는지 확인
        """
        # GIVEN: LifecycleManager 클래스 패치
        with patch('presenter.main_presenter.AppLifecycleManager') as MockLifecycle:
            mock_lifecycle_instance = MockLifecycle.return_value

            with patch('presenter.main_presenter.SettingsManager', return_value=mock_settings_manager):
                # WHEN: Presenter 생성
                _ = MainPresenter(mock_main_window)

                # THEN: LifecycleManager 인스턴스화 확인
                MockLifecycle.assert_called_once()

                # THEN: initialize_app 호출 확인
                mock_lifecycle_instance.initialize_app.assert_called_once()

    def test_signal_connections(self, mock_main_window, mock_settings_manager):
        """
        View와 Model 간의 시그널 연결 테스트

        Logic:
            - 초기화 후 View의 주요 시그널이 어딘가에 연결(connect)되었는지 확인
            - Mock 객체의 connect 메서드 호출 기록을 검사
        """
        with patch('presenter.main_presenter.SettingsManager', return_value=mock_settings_manager):
            # WHEN: Presenter 생성
            _ = MainPresenter(mock_main_window)

            # THEN: View 시그널 연결 확인
            mock_main_window.close_requested.connect.assert_called()
            mock_main_window.settings_save_requested.connect.assert_called()

            # THEN: 탭 변경 시그널 연결 확인 (UI 동기화용)
            mock_main_window.left_section.port_tab_panel.currentChanged.connect.assert_called()

    def test_data_handler_init(self, mock_main_window, mock_settings_manager):
        """
        DataTrafficHandler 초기화 및 타이머 시작 테스트

        Logic:
            - DataHandler가 View 참조를 가지고 생성되었는지 확인
            - 내부 타이머(QTimer)가 시작되었는지 간접 확인 (Mock 호출 등)
        """
        with patch('presenter.main_presenter.SettingsManager', return_value=mock_settings_manager):
            # QTimer를 패치하여 실제 타이머 동작 방지 및 호출 확인
            with patch('presenter.data_handler.QTimer') as MockTimer:
                # WHEN: Presenter 생성 -> DataHandler 생성
                presenter = MainPresenter(mock_main_window)

                # THEN: DataHandler가 View를 보유
                assert presenter.data_handler.view == mock_main_window

                # THEN: 타이머 시작 확인
                # DataHandler __init__ 에서 timer.start() 호출됨
                mock_timer_instance = MockTimer.return_value
                mock_timer_instance.start.assert_called()