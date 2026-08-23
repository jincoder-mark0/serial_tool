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
from unittest.mock import MagicMock

from presenter.packet_presenter import PacketPresenter
from view.panels.packet_panel import PacketPanel
from common.dtos import PacketEvent, PreferencesState, PacketViewData
from common.constants import ConfigKeys
from model.packet_parser import Packet


@pytest.fixture
def mock_panel():
    """
    PacketPanel(View)을 Mocking합니다.

    `spec`을 지정해 실제 `PacketPanel`에 없는 메서드 호출을 Mock이 삼키지 않게 한다
    (S-070). spec 없는 MagicMock은 어떤 이름이든 받아주므로, Presenter가 존재하지
    않는 View 메서드를 불러도 테스트가 통과한다 — S-067에서 실제로 그 틈으로
    `set_enabled()` 오타가 새어 나가 앱이 포트 탭을 바꿀 때마다 죽었다.
    """
    return MagicMock(spec=PacketPanel)


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
def presenter(mock_panel, mock_event_router, mock_settings_manager, qapp):
    """
    테스트 대상인 PacketPresenter 인스턴스를 생성하는 Fixture.

    S-061: PacketPresenter가 내부적으로 QTimer(버퍼 flush용)를 생성하므로
    QApplication 인스턴스가 필요하다 (test_auto_tx.py의 AutoTxScheduler 테스트와
    동일한 관례 — qapp 픽스처를 명시적으로 의존).
    """
    presenter = PacketPresenter(mock_panel, mock_event_router, mock_settings_manager)
    yield presenter
    presenter.stop()


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
            - on_packet_received 호출 (S-061: 즉시 반영되지 않고 버퍼링됨)
            - 타이머 flush(_flush_pending_packets)를 직접 호출해 반영시킴
              (data_handler._flush_rx_buffer_to_ui()를 직접 호출하는 기존 관례와 동일)
            - 뷰에 추가된 PacketViewData의 포맷(Hex, ASCII) 검증
        """
        # GIVEN: 테스트용 패킷 데이터
        packet = Packet(
            data=b'\x41\x42\x00\xff',
            timestamp=0,
            metadata={"type": "TEST_TYPE"},
        )

        event = PacketEvent(port="COM1", packet=packet)

        # WHEN: 패킷 수신 이벤트 처리 + flush
        presenter.on_packet_received(event)
        mock_panel.append_packet.assert_not_called()  # 버퍼링 확인 (즉시 반영 아님)
        presenter._flush_pending_packets()

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

        event = PacketEvent(port="COM1", packet=Packet(b'\x00', 0))

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
        presenter.on_packet_received(PacketEvent(port="COM1", packet=Packet(b'\x00', 0)))
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
        presenter.on_packet_received(PacketEvent(port="COM1", packet=Packet(b'\x00', 0)))
        mock_panel.append_packet.assert_not_called()

        # GIVEN: 캡처 켜기
        presenter.on_capture_toggled(True)

        # Check logic: Packet processed (S-061: 버퍼링 후 flush로 반영)
        presenter.on_packet_received(PacketEvent(port="COM1", packet=Packet(b'\x01', 0)))
        presenter._flush_pending_packets()
        mock_panel.append_packet.assert_called()


class TestPacketPresenterThrottle:
    """
    S-061: 패킷 View 반영 버퍼링(Throttling) 동작 검증

    실측(tasks/S-061-packet-view-throttle.md)에서 기본 설정 기준 고속 패킷
    버스트가 GUI 스레드를 수백ms~1초가량 블로킹하는 것을 확인해 도입한
    30ms 버퍼링이 다음을 만족하는지 검증한다:
        1. 순서 보장 (수신 순서 == 반영 순서)
        2. 누락 없음 (flush 전까지는 지연될 뿐 버려지지 않음)
        3. 종료(port_closed / stop) 시 잔여 flush
        4. Clear 시 지연 중인 버퍼도 함께 삭제 (Clear 이후 유령 패킷 재출현 방지)
    """

    @staticmethod
    def _make_event(index: int) -> PacketEvent:
        """식별 가능한 1바이트 패킷(순서 검증용) 생성."""
        return PacketEvent(
            port="COM1",
            packet=Packet(data=bytes([index % 256]), timestamp=0, metadata={"type": str(index)}),
        )

    def test_packets_are_buffered_not_applied_immediately(self, presenter, mock_panel):
        """on_packet_received 직후에는 View에 반영되지 않아야 한다 (버퍼링 확인)."""
        for i in range(10):
            presenter.on_packet_received(self._make_event(i))

        mock_panel.append_packet.assert_not_called()
        assert len(presenter._pending_packets) == 10

    def test_flush_applies_all_without_loss_and_in_order(self, presenter, mock_panel):
        """
        flush 시 버퍼링된 패킷이 수신 순서 그대로, 누락 없이 반영되어야 한다.

        버퍼링된 개수가 View 표시 버퍼 크기(mock_settings_manager 기준 100) 이하일 때는
        전량이 그대로 반영된다 — 버퍼 크기 초과 시의 동작은
        test_flush_caps_backlog_to_buffer_size_keeping_newest에서 별도 검증한다.
        """
        n = 80  # < buffer_size(100) — 잘림 없이 전량 반영되는 경우
        for i in range(n):
            presenter.on_packet_received(self._make_event(i))

        presenter._flush_pending_packets()

        assert mock_panel.append_packet.call_count == n  # 누락 없음
        applied_types = [call.args[0].packet_type for call in mock_panel.append_packet.call_args_list]
        assert applied_types == [str(i) for i in range(n)]  # 순서 보장
        assert presenter._pending_packets == []  # 버퍼가 비워짐

    def test_flush_caps_backlog_to_buffer_size_keeping_newest(self, presenter, mock_panel):
        """
        S-061 실측 결과, backlog를 통째로 flush하면 대형 버스트에서 단일 flush가
        1초 이상 걸릴 수 있음을 확인했다(개선 전보다 오히려 나쁜 경우). View의
        고정 크기 표시 버퍼(buffer_size=100)를 넘는 오래된 항목은 어차피 하나씩
        넣더라도 즉시 밀려나 화면에 한 번도 보이지 못하므로, flush는 최신
        buffer_size개만 반영해 최종 표시 결과는 그대로 유지하면서 단일 flush
        비용에 상한을 둔다.
        """
        n = 500  # buffer_size(100)보다 훨씬 큰 backlog
        for i in range(n):
            presenter.on_packet_received(self._make_event(i))

        presenter._flush_pending_packets()

        # 반영 횟수는 buffer_size로 상한이 걸린다 (n 전체가 아님).
        assert mock_panel.append_packet.call_count == 100
        applied_types = [call.args[0].packet_type for call in mock_panel.append_packet.call_args_list]
        # 최신 100개(400..499)만, 수신 순서 그대로 반영된다.
        assert applied_types == [str(i) for i in range(n - 100, n)]
        assert presenter._pending_packets == []

    def test_flush_with_empty_buffer_does_nothing(self, presenter, mock_panel):
        """버퍼가 비어있을 때 flush를 호출해도 View를 건드리지 않는다."""
        presenter._flush_pending_packets()
        mock_panel.append_packet.assert_not_called()

    def test_stop_flushes_remaining_buffer_and_stops_timer(self, presenter, mock_panel):
        """stop() 호출 시 잔여 버퍼가 flush되고, 이후 타이머가 더는 동작하지 않는다."""
        for i in range(5):
            presenter.on_packet_received(self._make_event(i))

        presenter.stop()

        assert mock_panel.append_packet.call_count == 5  # 잔여 flush (조용히 버려지지 않음)
        assert presenter._flush_timer.isActive() is False

    def test_port_closed_flushes_pending_buffer_immediately(self, presenter, mock_panel, mock_event_router):
        """포트가 닫히면 다음 30ms 주기를 기다리지 않고 즉시 flush된다."""
        for i in range(3):
            presenter.on_packet_received(self._make_event(i))
        mock_panel.append_packet.assert_not_called()

        # mock_event_router는 MagicMock이라 실제 시그널을 emit할 수 없으므로,
        # __init__에서 연결된 슬롯(port_closed.connect의 인자)을 직접 호출해
        # "port_closed 시그널이 발생했다"는 상황을 재현한다. 실제 PyQt 시그널
        # (port_closed = pyqtSignal(object))이 인자 없는 슬롯에 연결되면 emit 시
        # 초과 인자를 자동으로 버리므로, 여기서도 인자 없이 호출한다.
        connected_slot = mock_event_router.port_closed.connect.call_args[0][0]
        connected_slot()

        assert mock_panel.append_packet.call_count == 3

    def test_clear_requested_drops_pending_buffer(self, presenter, mock_panel):
        """Clear 요청 시 아직 flush되지 않은 버퍼도 함께 삭제되어야 한다 (유령 패킷 방지)."""
        for i in range(4):
            presenter.on_packet_received(self._make_event(i))

        presenter.on_clear_requested()
        presenter._flush_pending_packets()

        # Clear 시점에 지연 중이던 패킷들이 이후 flush에서 되살아나면 안 됨
        mock_panel.append_packet.assert_not_called()
        mock_panel.clear_view.assert_called_once()


class TestPacketChecksumVerification:
    """
    패킷 체크섬 검증 배선 (S-071).

    계산 자체의 정확성은 `tests/test_checksum.py`가 표준 시험 벡터로 고정한다.
    여기서는 **설정 → 오프셋 해석 → View DTO 반영** 경로만 본다.
    """

    @staticmethod
    def _settings(algorithm, offset=-1, lead=0, trail=0):
        """체크섬 설정을 돌려주는 SettingsManager Mock."""
        manager = MagicMock()

        def get_side_effect(key, default=None):
            mapping = {
                ConfigKeys.PACKET_BUFFER_SIZE: 100,
                ConfigKeys.PACKET_AUTOSCROLL: True,
                ConfigKeys.PACKET_REALTIME: True,
                ConfigKeys.PACKET_CHECKSUM_ALGORITHM: algorithm,
                ConfigKeys.PACKET_CHECKSUM_OFFSET: offset,
                ConfigKeys.PACKET_CHECKSUM_EXCLUDE_LEADING: lead,
                ConfigKeys.PACKET_CHECKSUM_EXCLUDE_TRAILING: trail,
            }
            return mapping.get(key, default)

        manager.get.side_effect = get_side_effect
        return manager

    def _make(self, mock_panel, mock_event_router, settings):
        from presenter.packet_presenter import PacketPresenter

        return PacketPresenter(mock_panel, mock_event_router, settings)

    def test_none_algorithm_reports_not_verified(self, mock_panel, mock_event_router):
        """알고리즘이 none이면 '검증하지 않음'(None)이어야 한다 — 통과로 위장하지 않는다."""
        p = self._make(mock_panel, mock_event_router, self._settings("none"))
        try:
            assert p._verify_checksum(b"\x01\x02\x03") is None
        finally:
            p.stop()

    def test_xor_trailing_byte_pass_and_fail(self, mock_panel, mock_event_router):
        """말미 1바이트 XOR 체크섬: 맞으면 True, 한 비트만 틀려도 False."""
        payload = b"\x01\x02\x03"
        # 주의: 0x01^0x02^0x03 == 0x00 이라 "틀린 값"으로 0x00을 쓰면 정답과 같아진다.
        # 이 테스트를 처음 쓸 때 실제로 그 실수를 했고, 테스트가 구현이 아니라
        # 데이터가 틀렸다고 알려줬다. 틀린 값은 정답에서 한 비트를 뒤집어 만든다.
        good = payload + bytes([0x01 ^ 0x02 ^ 0x03])
        bad = payload + bytes([0x01 ^ 0x02 ^ 0x03 ^ 0x01])

        # 체크섬 필드 자신은 계산에서 빼야 하므로 trailing 1바이트 제외
        p = self._make(mock_panel, mock_event_router, self._settings("xor", offset=-1, trail=1))
        try:
            assert p._verify_checksum(good) is True
            assert p._verify_checksum(bad) is False
        finally:
            p.stop()

    def test_leading_bytes_can_be_excluded(self, mock_panel, mock_event_router):
        """SOF 헤더를 계산에서 제외할 수 있어야 한다."""
        sof = b"\xAA\x55"
        body = b"\x10\x20\x30"
        packet = sof + body + bytes([0x10 ^ 0x20 ^ 0x30])

        p = self._make(
            mock_panel, mock_event_router, self._settings("xor", offset=-1, lead=2, trail=1)
        )
        try:
            assert p._verify_checksum(packet) is True
        finally:
            p.stop()

    def test_packet_too_short_is_not_verified_rather_than_failed(
        self, mock_panel, mock_event_router
    ):
        """
        체크섬 필드를 담기에 짧은 패킷은 '불일치'가 아니라 '검증 불가'여야 한다.

        파서 설정이 프로토콜과 안 맞을 때 모든 행이 빨갛게 물들면, 진짜 깨진 패킷을
        찾을 수 없다.
        """
        p = self._make(mock_panel, mock_event_router, self._settings("crc32", offset=-1))
        try:
            assert p._verify_checksum(b"\x01") is None
        finally:
            p.stop()

    def test_unknown_algorithm_is_not_verified(self, mock_panel, mock_event_router):
        """설정에 알 수 없는 알고리즘이 들어와도 죽지 않고 '검증 안 함'으로 넘어간다."""
        p = self._make(mock_panel, mock_event_router, self._settings("not_a_real_algorithm"))
        try:
            assert p._verify_checksum(b"\x01\x02\x03\x04") is None
        finally:
            p.stop()

    def test_result_reaches_view_dto(self, mock_panel, mock_event_router):
        """검증 결과가 PacketViewData까지 실려야 한다 (배선 확인)."""
        from model.packet_parser import Packet

        payload = b"\x01\x02\x03"
        wrong = (0x01 ^ 0x02 ^ 0x03) ^ 0x01  # 정답(0x00)에서 한 비트 뒤집기
        packet = Packet(data=payload + bytes([wrong]), timestamp=0.0)

        p = self._make(mock_panel, mock_event_router, self._settings("xor", offset=-1, trail=1))
        try:
            p.on_packet_received(PacketEvent(port="COM1", packet=packet))
            p._flush_pending_packets()
            mock_panel.append_packet.assert_called_once()
            view_data = mock_panel.append_packet.call_args[0][0]
            assert view_data.checksum_ok is False
        finally:
            p.stop()
