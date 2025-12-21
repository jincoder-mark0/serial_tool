"""
통합 테스트 리팩토링 모듈

애플리케이션의 주요 컴포넌트(MVP) 간의 상호작용 및 데이터 흐름을 검증합니다.

## WHY
* 단위 테스트만으로는 잡을 수 없는 컴포넌트 간 연결 오류 검출
* 실제 애플리케이션 시나리오(연결 -> 송신 -> 수신 -> 매크로) 위주의 검증
* 리팩토링 후 전체 시스템의 무결성 보장

## WHAT
* 시스템 초기화 및 의존성 주입 확인
* 포트 연결 및 해제 시나리오 (View -> Presenter -> Model)
* 수동 데이터 송신 흐름 (ManualPanel -> ConnectionController)
* 데이터 수신 및 UI 업데이트 흐름 (Fast Path 검증)
* 매크로 실행 및 중단 시나리오

## HOW
* MainWindow를 Mocking하여 GUI 렌더링 없이 로직 흐름만 검증
* MainPresenter를 진입점으로 하여 하위 컴포넌트들 자동 초기화
* 가짜 시리얼 포트(Mock Serial)를 통한 하드웨어 추상화
* qapp.processEvents()를 사용하여 비동기 시그널 처리 대기

pytest tests/test_integration_refactored.py -v
"""
import time
import pytest
from unittest.mock import MagicMock, patch

from PyQt5.QtCore import QCoreApplication

from presenter.main_presenter import MainPresenter
from common.dtos import (
    PortConfig,
    ManualCommand,
    PortDataEvent,
    MacroEntry,
    MacroExecutionRequest,
    MacroRepeatOption,
    PacketEvent
)
from common.constants import ConfigKeys


@pytest.fixture
def mock_main_window(qapp):
    """
    MainPresenter 초기화를 위한 가짜 MainWindow 객체를 생성합니다.

    복잡한 UI 계층 구조(Left/Right Section, Panels)를 MagicMock으로 구성하여
    Presenter가 초기화 과정에서 View 속성에 접근할 때 에러가 나지 않도록 합니다.

    Args:
        qapp: Qt Application 인스턴스 (conftest.py 제공).

    Returns:
        MagicMock: 구성된 가짜 MainWindow.
    """
    window = MagicMock()

    # 1. 하위 패널 Mocking
    window.port_view = MagicMock()           # PortPanel
    window.macro_view = MagicMock()          # MacroPanel

    # 2. 섹션 구조 Mocking (ManualControl, PacketPanel 등 접근용)
    window.left_section = MagicMock()
    window.left_section.manual_control_panel = MagicMock()
    window.left_section.port_tab_panel = MagicMock()
    window.left_section.system_log_widget = MagicMock()

    window.right_section = MagicMock()
    window.right_section.packet_panel = MagicMock()

    # 3. 주요 메서드 Mocking
    window.get_port_tabs_count.return_value = 1
    # 탭 변경 시그널
    window.left_section.port_tab_panel.currentChanged = MagicMock()

    return window


@pytest.fixture
def integration_system(mock_main_window, mock_serial_port, mock_settings_manager):
    """
    통합 테스트 환경을 구성합니다.
    MainPresenter를 생성하면 내부적으로 하위 Presenter와 Model이 모두 연결됩니다.

    Returns:
        tuple: (MainPresenter, MockMainWindow, ConnectionController)
    """
    # MainPresenter 생성 (내부적으로 LifecycleManager를 통해 초기화 수행)
    presenter = MainPresenter(mock_main_window)

    # 테스트 편의를 위해 Controller 참조 추출
    controller = presenter.connection_controller

    return presenter, mock_main_window, controller


class TestIntegrationRefactored:
    """
    시스템 통합 테스트 클래스
    """

    def test_system_initialization(self, integration_system):
        """
        시스템 초기화 및 의존성 연결 상태 검증

        Logic:
            - MainPresenter 생성 후 하위 컴포넌트들이 정상적으로 생성되었는지 확인
            - View의 시그널들이 Presenter에 연결되었는지 확인
        """
        presenter, window, controller = integration_system

        # THEN: 하위 Presenter 생성 확인
        assert presenter.port_presenter is not None
        assert presenter.macro_presenter is not None
        assert presenter.manual_control_presenter is not None
        assert presenter.packet_presenter is not None
        assert presenter.data_handler is not None

        # THEN: 주요 시그널 연결 확인
        # 예: ManualControlPanel의 전송 요청이 연결되었는가
        window.left_section.manual_control_panel.send_requested.connect.assert_called()

        # 예: PortView의 탭 변경 시그널 연결 확인
        window.left_section.port_tab_panel.currentChanged.connect.assert_called()

    def test_connection_flow(self, integration_system, sample_port_config):
        """
        포트 연결 및 해제 통합 시나리오

        Logic:
            1. View(PortPresenter)를 통해 연결 요청
            2. Controller -> Serial Open 수행 확인
            3. 성공 이벤트 발생 및 상태바 업데이트 확인
            4. 연결 해제 요청 및 종료 확인
        """
        presenter, window, controller = integration_system
        port_name = sample_port_config.port

        # GIVEN: PortView가 현재 선택된 포트 이름을 반환하도록 설정
        window.port_view.get_selected_port.return_value = port_name

        # ConnectionController에 포트 설정 주입 (검색 로직 우회)
        # 실제로는 PortManager가 해주지만 여기선 직접 설정
        controller.scan_ports() # Mock Serial이 포트 목록을 줄 것임 (conftest 참고 필요)
        # Mock Serial 환경이므로 강제로 Config 설정
        controller._port_configs[port_name] = sample_port_config

        # ---------------------------------------------------------
        # 1. 연결 (Connect)
        # ---------------------------------------------------------
        # WHEN: UI에서 연결 버튼 클릭 시뮬레이션
        presenter.port_presenter.connect_current_port()
        QCoreApplication.processEvents() # 비동기 처리 대기

        # THEN: 컨트롤러 상태 및 Serial Open 확인
        assert controller.is_connection_open(port_name) is True

        # THEN: UI 업데이트 호출 확인 (상태바, 메시지 등)
        # on_port_opened 핸들러가 호출되어 상태바 갱신
        window.update_status_bar_port.assert_called_with(port_name, True)

        # ---------------------------------------------------------
        # 2. 연결 해제 (Disconnect)
        # ---------------------------------------------------------
        # WHEN: 연결 해제 요청
        presenter.port_presenter.disconnect_current_port()
        QCoreApplication.processEvents()

        # THEN: 닫힘 확인
        assert controller.is_connection_open(port_name) is False
        window.update_status_bar_port.assert_called_with(port_name, False)

    def test_manual_send_flow(self, integration_system, sample_port_config):
        """
        수동 명령어 전송 통합 시나리오

        Logic:
            1. 포트 연결
            2. ManualPanel에서 전송 시그널 발생
            3. ConnectionController를 통해 실제(Mock) Write 수행 확인
            4. 로컬 에코(View) 출력 확인
        """
        presenter, window, controller = integration_system
        port_name = sample_port_config.port

        # GIVEN: 연결 상태 설정
        window.port_view.get_selected_port.return_value = port_name
        controller._port_configs[port_name] = sample_port_config
        presenter.port_presenter.connect_current_port()
        QCoreApplication.processEvents()

        # GIVEN: 전송할 명령어 DTO
        cmd = ManualCommand(
            command="TEST_MSG",
            hex_mode=False,
            local_echo_enabled=True,
            broadcast_enabled=False
        )

        # Mocking된 Serial 객체 가져오기 (Write 검증용)
        # controller.workers[port_name].serial_transport.serial 은 Mock 객체임
        worker = controller.workers[port_name]
        mock_serial = worker.serial_transport.serial

        # WHEN: ManualPresenter의 핸들러 직접 호출 (또는 시그널 emit 시뮬레이션)
        # 여기서는 Presenter 로직 검증을 위해 핸들러 호출
        presenter.manual_control_presenter.on_send_requested(cmd)
        QCoreApplication.processEvents()

        # THEN: Serial Write 호출 확인
        mock_serial.write.assert_called()
        # 인자 검증 (ASCII 인코딩된 바이트)
        args, _ = mock_serial.write.call_args
        assert args[0] == b"TEST_MSG"

        # THEN: 로컬 에코(View) 업데이트 확인
        # MainPresenter가 생성 시 ManualControlPresenter에 콜백(append_local_echo_data)을 전달함
        window.append_local_echo_data.assert_called_with(b"TEST_MSG")

    def test_data_reception_fast_path(self, integration_system, sample_port_config):
        """
        데이터 수신 및 UI 업데이트 (Fast Path) 검증

        Logic:
            1. 포트 데이터 수신 이벤트 발생 (ConnectionController -> DataHandler)
            2. DataHandler 버퍼링 확인
            3. 타이머/수동 플러시를 통해 UI 업데이트 확인
        """
        presenter, window, controller = integration_system
        port_name = sample_port_config.port

        # GIVEN: 데이터 이벤트 생성
        rx_data = b"HELLO_WORLD"
        event = PortDataEvent(port=port_name, data=rx_data)

        # WHEN: DataHandler의 Fast Path 슬롯 직접 호출 (시그널 전달 시뮬레이션)
        # 실제 앱에서는 controller.data_received 시그널이 연결됨
        presenter.data_handler.on_fast_data_received(event)

        # THEN: 즉시 UI 업데이트가 아니라 버퍼에 들어가야 함 (Throttling)
        assert port_name in presenter.data_handler._rx_buffer
        assert presenter.data_handler._rx_buffer[port_name] == rx_data

        # WHEN: 타이머에 의한 플러시 시뮬레이션 (직접 호출)
        presenter.data_handler._flush_rx_buffer_to_ui()

        # THEN: View의 append_rx_data 호출 확인
        window.append_rx_data.assert_called_once()

        # DTO(LogDataBatch) 검증
        call_args = window.append_rx_data.call_args[0][0]
        assert call_args.port == port_name
        assert call_args.data == rx_data

    def test_macro_execution_flow(self, integration_system, sample_port_config):
        """
        매크로 실행 및 중단 시나리오

        Logic:
            1. 매크로 시작 요청 (MacroPanel -> MacroPresenter)
            2. MacroRunner 시작 확인
            3. 매크로에 의한 데이터 전송 확인 (Mock Serial)
            4. 매크로 중단 요청 및 상태 변경 확인
        """
        presenter, window, controller = integration_system
        port_name = sample_port_config.port

        # GIVEN: 포트 연결
        window.port_view.get_selected_port.return_value = port_name
        controller._port_configs[port_name] = sample_port_config
        presenter.port_presenter.connect_current_port()
        QCoreApplication.processEvents()

        # Mock Serial 확보
        mock_serial = controller.workers[port_name].serial_transport.serial
        mock_serial.write.reset_mock()

        # GIVEN: 매크로 요청 DTO
        # 1번 인덱스의 매크로만 1회 실행
        request = MacroExecutionRequest(
            indices=[0],
            option=MacroRepeatOption(max_runs=1, delay_ms=0, broadcast_enabled=False)
        )

        # View Mocking: 매크로 리스트 데이터 제공
        entry = MacroEntry(enabled=True, command="MACRO_CMD", delay_ms=0)
        window.macro_view.macro_list.get_macro_entries.return_value = [entry]

        # ---------------------------------------------------------
        # 1. 매크로 시작 (Start)
        # ---------------------------------------------------------
        # WHEN: 매크로 시작 핸들러 호출
        presenter.macro_presenter.on_repeat_start(request)

        # 비동기 실행(Thread) 대기 (약간의 지연 필요)
        time.sleep(0.1)
        QCoreApplication.processEvents()

        # THEN: 상태바 업데이트 (매크로 실행 중)
        # MainPresenter.on_macro_started 호출 확인
        # (Window.show_status_message 등으로 검증 가능)

        # THEN: 데이터 전송 확인
        # 매크로 러너 -> MainPresenter -> ConnectionController -> Serial Write
        mock_serial.write.assert_called()
        assert b"MACRO_CMD" in mock_serial.write.call_args[0][0]

        # ---------------------------------------------------------
        # 2. 매크로 중단 (Stop)
        # ---------------------------------------------------------
        # WHEN: 매크로 정지
        presenter.macro_presenter.on_repeat_stop()
        QCoreApplication.processEvents()

        # THEN: 매크로 러너 정지 확인
        assert not presenter.macro_runner.isRunning()

    def test_packet_inspector_integration(self, integration_system):
        """
        패킷 인스펙터 통합 검증

        Logic:
            1. EventRouter를 통해 패킷 수신 이벤트 발생
            2. PacketPresenter가 이벤트를 받아 View(PacketPanel) 업데이트
        """
        presenter, window, controller = integration_system

        # GIVEN: 패킷 이벤트 생성
        # PacketParser가 만든 패킷 객체 Mocking
        mock_packet = MagicMock()
        mock_packet.raw_data = b'\xAA\xBB'
        mock_packet.type_name = "TEST_PKT"

        event = PacketEvent(packet=mock_packet)

        # WHEN: EventRouter 시그널 발생 (라우터는 MainPresenter 초기화 시 생성됨)
        # MainPresenter 내부의 event_router를 통해 패킷 수신 시뮬레이션
        presenter.event_router.packet_received.emit(event)
        QCoreApplication.processEvents()

        # THEN: PacketPanel에 데이터 추가 확인
        window.right_section.packet_panel.add_packet.assert_called_once()

        # DTO 값 검증
        view_data = window.right_section.packet_panel.add_packet.call_args[0][0]
        assert view_data.data_hex == "AA BB"
        assert view_data.packet_type == "TEST_PKT"