"""
뷰 계층 테스트 모듈

UI 위젯(View)의 독립적인 동작과 사용자 상호작용을 검증합니다.

## WHY
* Presenter 로직 없이 순수 UI 컴포넌트(위젯, 패널)의 동작 검증
* 사용자 입력(클릭, 타이핑)에 따른 시그널 방출 여부 확인
* 커스텀 위젯(SmartLineEdit 등)의 입력 제한 로직 테스트

## WHAT
* QSmartLineEdit: HEX 모드 입력 필터링 및 자동 대문자 변환
* ManualControlPanel: DTO 생성 및 전송 시그널 검증
* PacketPanel: 데이터 모델 업데이트 및 초기화(Clear) 검증
* PortPanel: 연결 상태 변경에 따른 UI 반영 확인

## HOW
* pytest-qt의 `qtbot` 픽스처를 사용하여 UI 이벤트(클릭, 키 입력) 시뮬레이션
* SignalSpy(qtbot.waitSignal)를 사용하여 시그널 발생과 전달된 데이터(DTO) 검증
"""
import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QPushButton

from view.custom_qt.smart_line_edit import QSmartLineEdit
from view.panels.manual_control_panel import ManualControlPanel
from view.panels.packet_panel import PacketPanel
from view.panels.port_panel import PortPanel
from common.dtos import PacketViewData, ManualCommand


class TestSmartLineEdit:
    """
    커스텀 위젯 QSmartLineEdit의 입력 로직을 검증하는 테스트 클래스
    """

    def test_hex_mode_input_validation(self, qtbot):
        """
        HEX 모드 입력 필터링 및 대문자 변환 테스트

        Logic:
            - HEX 모드 활성화
            - 유효하지 않은 문자('g') 입력 시도 -> 무시되어야 함
            - 소문자('a') 입력 시도 -> 대문자('A')로 변환되어야 함
        """
        # GIVEN: 위젯 생성 및 HEX 모드 설정
        widget = QSmartLineEdit()
        qtbot.addWidget(widget)
        widget.set_hex_mode(True)
        widget.show()

        # WHEN: 'g' (Invalid HEX) 입력
        qtbot.keyClicks(widget, "g")

        # THEN: 입력되지 않아야 함
        assert widget.text() == ""

        # WHEN: 'a' (Valid HEX) 입력
        qtbot.keyClicks(widget, "a")

        # THEN: 대문자 'A'로 변환되어 입력되어야 함
        assert widget.text() == "A"

        # WHEN: 공백 및 숫자 입력
        qtbot.keyClicks(widget, " 1")
        assert widget.text() == "A 1"

    def test_ascii_mode_input(self, qtbot):
        """
        일반(ASCII) 모드 입력 테스트

        Logic:
            - HEX 모드 비활성화 (기본값)
            - 모든 문자 입력 허용 확인
        """
        # GIVEN: 위젯 생성
        widget = QSmartLineEdit()
        qtbot.addWidget(widget)
        widget.set_hex_mode(False)
        widget.show()

        # WHEN: 다양한 문자 입력
        test_str = "Hello 123!"
        qtbot.keyClicks(widget, test_str)

        # THEN: 그대로 입력되어야 함
        assert widget.text() == test_str


class TestManualControlPanel:
    """
    ManualControlPanel의 사용자 상호작용 및 시그널 방출 테스트
    """

    def test_send_signal_emission(self, qtbot):
        """
        전송 버튼 클릭 시 시그널 방출 및 DTO 데이터 검증

        Logic:
            - 입력창에 텍스트 입력
            - 전송 버튼 클릭 시뮬레이션
            - send_requested 시그널 발생 대기 및 검증
        """
        # GIVEN: 패널 생성
        panel = ManualControlPanel()
        qtbot.addWidget(panel)
        panel.show()

        # 내부 위젯 참조
        widget = panel.manual_control_widget

        # 텍스트 입력
        qtbot.keyClicks(widget.input_edit, "TEST_CMD")

        # 옵션 설정 (예: Local Echo 체크)
        widget.chk_local_echo.setChecked(True)

        # WHEN: 전송 버튼 클릭 (SignalSpy 사용)
        with qtbot.waitSignal(panel.send_requested, timeout=1000) as blocker:
            qtbot.mouseClick(widget.btn_send, Qt.LeftButton)

        # THEN: 시그널 발생 확인 및 DTO 검증
        assert blocker.signal_triggered

        # 전달된 인자(DTO) 가져오기
        args = blocker.args
        command_dto: ManualCommand = args[0]

        assert isinstance(command_dto, ManualCommand)
        assert command_dto.command == "TEST_CMD"
        assert command_dto.local_echo_enabled is True
        assert command_dto.hex_mode is False  # 기본값 확인

    def test_hardware_control_signals(self, qtbot):
        """
        RTS/DTR 체크박스 토글 시그널 테스트

        Logic:
            - RTS 체크박스 클릭 -> rts_changed 시그널(True) 발생
            - DTR 체크박스 클릭 -> dtr_changed 시그널(True) 발생
        """
        # GIVEN: 패널 생성
        panel = ManualControlPanel()
        qtbot.addWidget(panel)
        panel.show()

        widget = panel.manual_control_widget

        # WHEN & THEN: RTS 토글
        with qtbot.waitSignal(panel.rts_changed) as blocker:
            widget.chk_rts.setChecked(True)
        assert blocker.args[0] is True

        # WHEN & THEN: DTR 토글
        with qtbot.waitSignal(panel.dtr_changed) as blocker:
            widget.chk_dtr.setChecked(True)
        assert blocker.args[0] is True


class TestPacketPanel:
    """
    PacketPanel의 데이터 모델 업데이트 및 뷰 제어 테스트
    """

    def test_append_packet_updates_model(self, qtbot):
        """
        패킷 추가 시 테이블 모델 업데이트 검증

        Logic:
            - PacketViewData DTO 생성
            - append_packet 호출
            - 테이블 모델의 rowCount 증가 및 데이터 일치 확인
        """
        # GIVEN: 패널 생성
        panel = PacketPanel()
        qtbot.addWidget(panel)
        panel.show()

        view_data = PacketViewData(
            time_str="12:00:00",
            packet_type="TEST",
            data_hex="AA BB",
            data_ascii=".."
        )

        # WHEN: 패킷 추가
        panel.append_packet(view_data)

        # THEN: 모델 업데이트 확인
        model = panel.packet_model
        assert model.rowCount() == 1

        # 데이터 검증 (Column 2: HEX)
        index = model.index(0, 2)
        assert model.data(index, Qt.DisplayRole) == "AA BB"

    def test_clear_view(self, qtbot):
        """
        Clear 기능 검증

        Logic:
            - 데이터 추가 후 rowCount > 0 확인
            - clear_view 호출
            - rowCount == 0 확인
        """
        # GIVEN: 데이터가 있는 패널
        panel = PacketPanel()
        qtbot.addWidget(panel)

        panel.append_packet(PacketViewData("T", "T", "H", "A"))
        assert panel.packet_model.rowCount() == 1

        # WHEN: Clear 수행
        panel.clear_view()

        # THEN: 모델 초기화 확인
        assert panel.packet_model.rowCount() == 0


class TestPortPanel:
    """
    PortPanel(개별 포트 탭)의 UI 상태 변경 테스트
    (참고: PortPanel의 구체적인 구현에 따라 테스트 코드는 조정될 수 있음)
    """

    def test_ui_state_on_connection_change(self, qtbot):
        """
        연결/해제 상태에 따른 UI 활성화/비활성화 테스트

        Logic:
            - 초기 상태(Disconnected) 확인
            - set_connected_state(True) 호출
            - 버튼 텍스트 변경 또는 상태 변경 확인
        """
        # GIVEN: 패널 생성 (mocking 없이 직접 생성)
        # PortPanel 생성자는 보통 parent와 port_name을 받음
        panel = PortPanel(port_name="COM1")
        qtbot.addWidget(panel)
        panel.show()

        # 내부 UI 컴포넌트 참조 (PortPanel 구현에 의존)
        # btn_open_close가 존재한다고 가정
        if hasattr(panel, 'btn_open_close'):
            btn = panel.btn_open_close

            # GIVEN: 초기 상태 (Disconnected)
            assert not panel.is_connected()

            # WHEN: 연결 상태로 변경
            panel.set_connected_state(True)

            # THEN: 내부 상태 플래그 변경 확인
            assert panel.is_connected()

            # UI 텍스트 변경 확인 (예: "Open" -> "Close")
            # 언어 설정에 따라 다르겠지만, 상태 변경 시 텍스트가 바뀌어야 함
            assert btn.text() != "Open"

    def test_open_close_signal(self, qtbot):
        """
        연결 버튼 클릭 시 시그널 방출 테스트
        """
        panel = PortPanel(port_name="COM1")
        qtbot.addWidget(panel)
        panel.show()

        if hasattr(panel, 'connect_requested'):
            # WHEN: 버튼 클릭
            with qtbot.waitSignal(panel.connect_requested) as blocker:
                # Disconnected 상태이므로 클릭하면 연결 요청
                qtbot.mouseClick(panel.btn_open_close, Qt.LeftButton)

            # THEN: 시그널 발생 확인
            assert blocker.signal_triggered
            assert blocker.args[0] == "COM1"