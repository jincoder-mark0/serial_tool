"""
수동 제어 프레젠터 테스트 모듈

ManualControlPresenter의 비즈니스 로직을 검증합니다.

## WHY
* 사용자 입력에 대한 데이터 가공(Prefix, Hex 등) 로직 검증
* 연결 상태에 따른 전송(Broadcast/Single) 분기 처리 확인
* UI 상태 저장 및 복원 기능의 정확성 보장

## WHAT
* on_send_requested: 명령어 전송 시나리오 (성공, 실패, 옵션 적용)
* 하드웨어 제어: RTS/DTR 시그널 전달 확인
* 상태 관리: get_state/apply_state 데이터 무결성 검증

## HOW
* unittest.mock.MagicMock을 사용하여 View와 Model(Connection)을 격리
* SettingsManager를 Mocking하여 설정값(Prefix/Suffix) 주입
* 다양한 ManualCommand DTO 케이스를 생성하여 로직 커버리지 확보

pytest tests/test_presenter_manual_control.py -v
"""
import pytest
from unittest.mock import MagicMock, patch

from presenter.manual_control_presenter import ManualControlPresenter
from common.dtos import ManualCommand, ManualControlState
from common.constants import ConfigKeys


@pytest.fixture
def mock_panel():
    """
    ManualControlPanel(View)을 Mocking합니다.
    """
    return MagicMock()


@pytest.fixture
def mock_echo_callback():
    """
    로컬 에코 콜백 함수를 Mocking합니다.
    """
    return MagicMock()


@pytest.fixture
def mock_get_port_callback():
    """
    활성 포트 조회 콜백을 Mocking합니다.
    기본값으로 'COM1'을 반환하도록 설정합니다.
    """
    mock = MagicMock()
    mock.return_value = "COM1"
    return mock


@pytest.fixture
def presenter(mock_panel, mock_serial_port, mock_echo_callback, mock_get_port_callback):
    """
    테스트 대상인 ManualControlPresenter 인스턴스를 생성하는 Fixture.
    ConnectionController는 Mocking된 시리얼 포트를 사용하는 실제 인스턴스 대신
    완전히 Mocking된 컨트롤러를 주입하여 테스트 범위를 좁힙니다.
    """
    # ConnectionController 전체를 Mocking
    mock_controller = MagicMock()
    mock_controller.is_connection_open.return_value = True

    presenter = ManualControlPresenter(
        panel=mock_panel,
        connection_controller=mock_controller,
        local_echo_callback=mock_echo_callback,
        get_active_port_callback=mock_get_port_callback
    )
    return presenter


class TestManualControlPresenter:
    """
    ManualControlPresenter의 기능을 검증하는 테스트 클래스
    """

    def test_init_connection(self, presenter, mock_panel):
        """
        초기화 및 시그널 연결 테스트

        Logic:
            - Presenter 초기화 시 View의 시그널(send_requested 등)이
              Presenter의 슬롯에 연결되었는지 확인
        """
        # GIVEN: Fixture에 의해 초기화됨

        # THEN: 시그널 연결 확인 (MagicMock은 connect 호출을 기록함)
        mock_panel.send_requested.connect.assert_called()
        # DTR/RTS 시그널 연결 확인 (조건부 연결이므로 속성 존재 시)
        if hasattr(mock_panel, 'dtr_changed'):
            mock_panel.dtr_changed.connect.assert_called()

    def test_send_empty_command(self, presenter):
        """
        빈 명령어 전송 시도 테스트 (HEX 모드 아님)

        Logic:
            - 빈 문자열 커맨드 DTO 생성
            - on_send_requested 호출
            - 전송 메서드가 호출되지 않아야 함
        """
        # GIVEN: 빈 명령어
        cmd = ManualCommand(command="", hex_mode=False)

        # WHEN: 전송 요청
        presenter.on_send_requested(cmd)

        # THEN: 전송 로직이 실행되지 않아야 함
        presenter.connection_controller.send_data.assert_not_called()

    def test_send_single_port_success(self, presenter, mock_echo_callback):
        """
        단일 포트 데이터 전송 성공 테스트

        Logic:
            - 유효한 명령어 DTO 생성
            - 활성 포트가 있고 연결된 상태 가정
            - 전송 후 send_data 호출 및 로컬 에코 콜백 호출 확인
        """
        # GIVEN: 명령어 및 설정
        cmd = ManualCommand(
            command="TEST",
            hex_mode=False,
            local_echo_enabled=True,
            broadcast_enabled=False
        )

        # WHEN: 전송 요청
        presenter.on_send_requested(cmd)

        # THEN: 데이터 전송 확인 (ASCII 인코딩)
        presenter.connection_controller.send_data.assert_called_once()
        args = presenter.connection_controller.send_data.call_args
        assert args[0][0] == "COM1"       # Port
        assert args[0][1] == b"TEST"      # Data

        # THEN: 로컬 에코 확인
        mock_echo_callback.assert_called_once_with(b"TEST")

    def test_send_broadcast_success(self, presenter, mock_echo_callback):
        """
        브로드캐스트 전송 성공 테스트

        Logic:
            - broadcast_enabled=True 설정된 DTO
            - send_broadcast_data 메서드 호출 확인
        """
        # GIVEN: 브로드캐스트 명령어
        cmd = ManualCommand(
            command="BCAST",
            hex_mode=False,
            broadcast_enabled=True,
            local_echo_enabled=True
        )

        # WHEN: 전송 요청
        presenter.on_send_requested(cmd)

        # THEN: 브로드캐스트 메서드 호출 확인
        presenter.connection_controller.send_broadcast_data.assert_called_once_with(b"BCAST")

        # 단일 전송 메서드는 호출되지 않아야 함
        presenter.connection_controller.send_data.assert_not_called()

        # 로컬 에코 확인
        mock_echo_callback.assert_called_once()

    def test_send_with_prefix_suffix(self, presenter):
        """
        Prefix/Suffix 적용 전송 테스트

        Logic:
            - SettingsManager를 Mocking하여 Prefix/Suffix 값 설정
            - DTO에서 prefix/suffix 활성화
            - 최종 전송 데이터에 결합되었는지 확인
        """
        # GIVEN: 설정 Mocking (SettingsManager.get 메서드 패치)
        with patch.object(presenter.settings_manager, 'get') as mock_get:
            def get_side_effect(key, default=None):
                if key == ConfigKeys.COMMAND_PREFIX:
                    return "<"
                if key == ConfigKeys.COMMAND_SUFFIX:
                    return ">"
                return default
            mock_get.side_effect = get_side_effect

            cmd = ManualCommand(
                command="DATA",
                prefix_enabled=True,
                suffix_enabled=True,
                hex_mode=False
            )

            # WHEN: 전송 요청
            presenter.on_send_requested(cmd)

            # THEN: 앞뒤에 문자가 붙어서 전송되어야 함
            presenter.connection_controller.send_data.assert_called_once()
            sent_data = presenter.connection_controller.send_data.call_args[0][1]
            assert sent_data == b"<DATA>"

    def test_send_hex_mode(self, presenter):
        """
        HEX 모드 전송 테스트

        Logic:
            - HEX 문자열("AA BB") 입력
            - hex_mode=True 설정
            - 바이트 변환 결과(b'\xaa\xbb') 확인
        """
        # GIVEN: HEX 명령어
        cmd = ManualCommand(
            command="AA BB CC",
            hex_mode=True
        )

        # WHEN: 전송 요청
        presenter.on_send_requested(cmd)

        # THEN: 바이너리 데이터 전송 확인
        presenter.connection_controller.send_data.assert_called_once()
        sent_data = presenter.connection_controller.send_data.call_args[0][1]
        assert sent_data == b'\xaa\xbb\xcc'

    def test_send_fail_no_active_port(self, presenter, mock_get_port_callback):
        """
        활성 포트가 없을 때 전송 실패 테스트

        Logic:
            - get_active_port_callback이 None 반환하도록 설정
            - 전송 요청 시 send_data가 호출되지 않아야 함
        """
        # GIVEN: 활성 포트 없음
        mock_get_port_callback.return_value = None
        cmd = ManualCommand(command="TEST")

        # WHEN: 전송 요청
        presenter.on_send_requested(cmd)

        # THEN: 전송되지 않음
        presenter.connection_controller.send_data.assert_not_called()

    def test_hardware_control_toggle(self, presenter):
        """
        하드웨어 제어 신호(DTR, RTS) 토글 테스트

        Logic:
            - on_dtr_changed / on_rts_changed 호출
            - Controller의 set_dtr / set_rts 호출 확인
        """
        # GIVEN: DTR ON 요청
        presenter.on_dtr_changed(True)
        # THEN: Controller 호출 확인
        presenter.connection_controller.set_dtr.assert_called_once_with(True)

        # GIVEN: RTS OFF 요청
        presenter.on_rts_changed(False)
        # THEN: Controller 호출 확인
        presenter.connection_controller.set_rts.assert_called_once_with(False)

    def test_state_management(self, presenter, mock_panel):
        """
        상태 저장(get_state) 및 복원(apply_state) 테스트

        Logic:
            - get_state 호출 시 패널의 get_state 호출 확인
            - apply_state 호출 시 패널의 apply_state 호출 확인
        """
        # 1. Get State Test
        # WHEN
        presenter.get_state()
        # THEN
        mock_panel.get_state.assert_called_once()

        # 2. Apply State Test
        # GIVEN
        dummy_state = ManualControlState(input_text="Saved")
        # WHEN
        presenter.apply_state(dummy_state)
        # THEN
        mock_panel.apply_state.assert_called_once_with(dummy_state)

    def test_update_local_echo_setting(self, presenter, mock_panel):
        """
        글로벌 설정 변경에 따른 로컬 에코 UI 동기화 테스트

        Logic:
            - update_local_echo_setting 호출
            - 패널의 set_local_echo_checked 메서드 호출 확인
        """
        # WHEN
        presenter.update_local_echo_setting(True)

        # THEN
        # Mock Panel에 해당 메서드가 있다고 가정하고 호출 확인
        # (실제 Panel 구현에 의존하므로 Mock에 메서드 정의 필요할 수 있음)
        # 여기서는 getattr이나 MagicMock 특성을 이용해 호출 기록만 확인
        if hasattr(mock_panel, 'set_local_echo_checked'):
             mock_panel.set_local_echo_checked.assert_called_once_with(True)