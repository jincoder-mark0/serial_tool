"""
패킷 프레젠터 테스트 모듈

PacketPresenter의 비즈니스 로직과 뷰 제어 흐름을 검증합니다.

## WHY
* 실시간 패킷 데이터가 UI에 올바른 형식(Hex/ASCII)으로 표시되는지 확인
* 캡처 일시정지/재개 기능이 데이터 유입을 정확히 제어하는지 검증
* 전역 설정 변경 시 뷰(View)의 상태가 동기화되는지 보장

## WHAT
* on_packet_received: 수신 데이터의 포맷팅 및 뷰 추가 로직
* 캡처 제어: _is_capturing 플래그에 따른 이벤트 필터링
* 설정 변경: 버퍼 크기 및 오토스크롤 설정 반영
* 사용자 액션: Clear, Toggle Capture 요청 처리

## HOW
* unittest.mock.MagicMock을 사용하여 PacketPanel(View)과 EventRouter를 격리
* 가짜 패킷 객체(Mock Packet)를 생성하여 데이터 파싱 로직 테스트
* PreferencesState DTO를 주입하여 설정 변경 시나리오 시뮬레이션

pytest tests/test_presenter_packet.py -v
"""
import pytest
from unittest.mock import MagicMock, call

from presenter.packet_presenter import PacketPresenter
from common.dtos import PacketEvent, PreferencesState, PacketViewData
from common.constants import ConfigKeys


@pytest.fixture
def mock_panel():
    """PacketPanel(View)을 Mocking합니다."""
    return MagicMock()


@pytest.fixture
def mock_event_router():
    """EventRouter를 Mocking합니다."""
    return MagicMock()


@pytest.fixture
def mock_settings_manager():
    """
    SettingsManager를 Mocking합니다.
    초기 설정값을 반환하도록 side_effect 또는 return_value를 설정합니다.
    """
    manager = MagicMock()

    # get 메서드 호출 시 반환할 기본값 설정
    def get_side_effect(key, default=None):
        if key == ConfigKeys.PACKET_BUFFER_SIZE:
            return 100
        if key == ConfigKeys.PACKET_AUTOSCROLL:
            return True
        if key == ConfigKeys.PACKET_REALTIME:
            return True
        return default

    manager.get.side_effect = get_side_effect
    return manager


@pytest.fixture
def presenter(mock_panel, mock_event_router, mock_settings_manager):
    """
    테스트 대상인 PacketPresenter 인스턴스를 생성하는 Fixture.
    """
    return PacketPresenter(mock_panel, mock_event_router, mock_settings_manager)


class TestPacketPresenter:
    """
    PacketPresenter의 기능을 검증하는 테스트 클래스
    """

    def test_initialization(self, presenter, mock_panel, mock_event_router):
        """
        초기화 시 설정 적용 및 시그널 연결 테스트

        Logic:
            - 생성자 호출 시(Fixture) 초기 설정값(버퍼, 오토스크롤)이 뷰에 적용되었는지 확인
            - View와 EventRouter의 시그널이 Presenter에 연결되었는지 확인
        """
        # GIVEN: Presenter 초기화됨 (Fixture)

        # THEN: 초기 설정 적용 확인 (SettingsManager Mock 값 기준)
        mock_panel.set_buffer_size.assert_called_with(100)
        mock_panel.set_autoscroll.assert_called_with(True)
        mock_panel.set_capture_state.assert_called_with(True)

        # THEN: 시그널 연결 확인
        mock_panel.clear_requested.connect.assert_called()
        mock_panel.capture_toggled.connect.assert_called()
        mock_event_router.packet_received.connect.assert_called()
        mock_event_router.settings_changed.connect.assert_called()

    def test_packet_processing(self, presenter, mock_panel):
        """
        패킷 수신 및 포맷팅 로직 테스트

        Logic:
            - Mock Packet 객체를 포함한 PacketEvent 생성
            - on_packet_received 호출
            - 뷰에 추가된 PacketViewData의 포맷(Hex, ASCII) 검증
        """
        # GIVEN: 테스트용 패킷 데이터
        mock_packet = MagicMock()
        mock_packet.raw_data = b'\x41\x42\x00\xff'  # 'AB' + NULL + Non-printable
        mock_packet.type_name = "TEST_TYPE"

        event = PacketEvent(packet=mock_packet)

        # WHEN: 패킷 수신 이벤트 처리
        presenter.on_packet_received(event)

        # THEN: 뷰에 데이터가 추가되어야 함
        mock_panel.append_packet.assert_called_once()

        # 전달된 DTO 검증
        args = mock_panel.append_packet.call_args[0]
        view_data: PacketViewData = args[0]

        assert isinstance(view_data, PacketViewData)
        assert view_data.packet_type == "TEST_TYPE"
        assert view_data.data_hex == "41 42 00 FF"  # Hex formatting check
        assert view_data.data_ascii == "AB.."       # ASCII filtering check (. for non-printable)
        assert view_data.time_str is not None       # Timestamp check

    def test_packet_ignored_when_not_capturing(self, presenter, mock_panel):
        """
        캡처 중지 상태에서 패킷 무시 테스트

        Logic:
            - 캡처 상태를 False로 변경
            - 패킷 이벤트 발생
            - 뷰 업데이트 메서드가 호출되지 않아야 함
        """
        # GIVEN: 캡처 중지
        presenter.on_capture_toggled(False)

        mock_packet = MagicMock()
        mock_packet.raw_data = b'\x00'
        event = PacketEvent(packet=mock_packet)

        # WHEN: 패킷 수신
        presenter.on_packet_received(event)

        # THEN: 뷰에 추가되지 않음
        mock_panel.append_packet.assert_not_called()

    def test_settings_update(self, presenter, mock_panel):
        """
        전역 설정 변경 시 뷰 동기화 테스트

        Logic:
            - 변경된 설정값을 담은 PreferencesState DTO 생성
            - on_settings_changed 호출
            - 뷰의 설정 메서드(set_buffer_size 등) 호출 확인
        """
        # GIVEN: 변경된 설정 상태
        new_state = PreferencesState(
            packet_buffer_size=500,
            packet_autoscroll=False,
            packet_realtime=False
            # 나머지 필드는 기본값 또는 무관
        )

        # WHEN: 설정 변경 알림
        presenter.on_settings_changed(new_state)

        # THEN: 뷰 설정 업데이트 확인
        mock_panel.set_buffer_size.assert_called_with(500)
        mock_panel.set_autoscroll.assert_called_with(False)
        mock_panel.set_capture_state.assert_called_with(False)

        # 내부 상태 변경 확인 (캡처 플래그가 꺼졌으므로 패킷 무시 확인)
        mock_packet = MagicMock()
        presenter.on_packet_received(PacketEvent(packet=mock_packet))
        mock_panel.append_packet.assert_not_called()

    def test_clear_view(self, presenter, mock_panel):
        """
        Clear 요청 처리 테스트

        Logic:
            - on_clear_requested 호출
            - 뷰의 clear_view 메서드 호출 확인
        """
        # WHEN: Clear 요청
        presenter.on_clear_requested()

        # THEN: 뷰 초기화 호출
        mock_panel.clear_view.assert_called_once()

    def test_capture_toggle(self, presenter, mock_panel):
        """
        캡처 토글 요청 처리 테스트

        Logic:
            - on_capture_toggled 호출
            - 내부 상태 변경 확인 (패킷 수신 여부로 간접 확인)
        """
        # GIVEN: 캡처 끄기
        presenter.on_capture_toggled(False)

        # Check logic: Packet ignored
        presenter.on_packet_received(PacketEvent(packet=MagicMock()))
        mock_panel.append_packet.assert_not_called()

        # GIVEN: 캡처 켜기
        presenter.on_capture_toggled(True)

        # Check logic: Packet processed
        mock_packet = MagicMock()
        mock_packet.raw_data = b'\x01'
        presenter.on_packet_received(PacketEvent(packet=mock_packet))
        mock_panel.append_packet.assert_called()