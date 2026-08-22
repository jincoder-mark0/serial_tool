"""
S-059 회귀 테스트: 앱 종료 시 RX 데이터 로거 미정리 결함

## WHY
* `core/data_logger.py`의 `DataLoggerManager.stop_all()`이 저장소 어디에서도
  호출되지 않았다 (`presenter/`·`main.py`·`view/` 전수 확인, 0건). 로깅을 켠 채
  앱을 종료하면 데몬 쓰기 스레드가 프로세스 종료와 함께 강제로 죽어 큐에 남은
  데이터가 유실되고 파일이 정상적으로 닫히지 않는다.
* `stop_logging(port)`을 직접 호출하는 단위 테스트로는 이 결함(호출 자체가
  없음)을 잡을 수 없다 — 반드시 `MainPresenter.on_close_requested()`라는
  실제 종료 경로를 태워야 한다.
* 정리 순서도 중요하다: 로거를 연결보다 먼저 닫으면 워커 스레드 종료 직전
  (`ConnectionWorker.run()`의 `finally`) 마지막으로 flush되는 잔여 RX 배치가
  이미 닫힌 파일을 향해 가게 되어 유실된다. 따라서 (1) 연결 종료 ->
  (2) `QCoreApplication.processEvents()`로 교차 스레드 큐잉 시그널 배송 ->
  (3) 로거 정리 순서가 되어야 한다(`presenter/main_presenter.py`
  `on_close_requested()`의 S-059 주석 참조).

## WHAT
* `test_shutdown_stops_data_logger_and_preserves_written_bytes`:
  주 결함 회귀 - LOOPBACK 연결로 실제 Fast Path를 통해 파일에 데이터가 쓰인 뒤
  `on_close_requested()`가 로거를 정지시키고(`is_logging` False), 파일 내용이
  유실 없이 보존되는지 확인한다.
* `test_shutdown_flushes_pending_leftover_batch_before_closing_logger`:
  정리 순서 회귀 - 배치 임계값/타임아웃을 아주 크게 monkeypatch해 정상 배치
  플러시가 절대 먼저 일어나지 않게 만든 뒤, 워커 스레드 종료 직전 `finally`가
  flush하는 "마지막 잔여 배치"가 `on_close_requested()`의 `processEvents()` 덕에
  로거가 닫히기 전에 파일까지 도달하는지 결정론적으로 검증한다.
* `test_shutdown_without_any_active_logging_does_not_raise`: 로깅 중이 아닐 때도
  종료 경로가 예외 없이 통과한다.

## HOW
* `tests/test_text_log_writer.py`와 동일한 패턴 — View는 MagicMock, `SettingsManager`는
  `mock_settings_manager`(실제 임시 경로) 주입한 진짜 `MainPresenter`를 사용해
  `on_close_requested()`가 실제로 끝까지 실행되도록 한다.
* 연결은 `tests/test_tx_flush.py`와 동일하게 `LOOPBACK_PORT_NAME` 더미 포트를 사용해
  실제 `QThread` 기반 `ConnectionWorker`를 구동한다 (Mock 아님, 실제 스레드).
* 순서 회귀 테스트는 `model.connection_worker.BATCH_SIZE_THRESHOLD` /
  `BATCH_TIMEOUT_MS`를 매우 크게 monkeypatch하여 "정상 배치 타임아웃에 의한
  우연한 통과"를 배제하고, `worker.transport.in_waiting == 0`을 폴링해 에코된
  바이트가 이미 워커 내부 배치 버퍼로 읽혀 들어간 뒤(즉 아직 emit되지 않은 채
  대기 중인 상태)에만 종료를 트리거하여 레이스를 제거한다.
"""
from unittest.mock import MagicMock, patch

import pytest

from common.constants import LOOPBACK_PORT_NAME
from common.dtos import PortConfig, MainWindowState
from common.enums import SerialParity, SerialStopBits, SerialFlowControl
from core.data_logger import data_logger_manager
from presenter.main_presenter import MainPresenter


@pytest.fixture
def loopback_config() -> PortConfig:
    """LOOPBACK 더미 포트용 PortConfig DTO (tests/test_tx_flush.py와 동일)."""
    return PortConfig(
        port=LOOPBACK_PORT_NAME,
        baudrate=115200,
        bytesize=8,
        parity=SerialParity.NONE.value,
        stopbits=SerialStopBits.ONE.value,
        flowctrl=SerialFlowControl.NONE.value,
    )


@pytest.fixture
def mock_main_window():
    """
    MainPresenter 초기화에 필요한 최소 MainWindow Mock
    (`tests/test_text_log_writer.py`의 fixture와 동일한 패턴).
    """
    view = MagicMock()

    view.left_section = MagicMock()
    view.right_section = MagicMock()
    view.left_section.port_tab_panel = MagicMock()
    view.left_section.port_tab_panel.currentIndex.return_value = 0
    view.left_section.port_tab_panel.widget.return_value = MagicMock()
    view.left_section.manual_control_panel = MagicMock()
    view.left_section.system_log_widget = MagicMock()
    view.right_section.packet_panel = MagicMock()
    view.macro_view = MagicMock()
    view.port_view = MagicMock()

    view.manual_control_view = MagicMock()
    view.manual_control_view.get_input_text.return_value = ""
    view.manual_control_view.is_hex_mode.return_value = False
    view.manual_control_view.is_prefix_enabled.return_value = False
    view.manual_control_view.is_suffix_enabled.return_value = False
    view.manual_control_view.is_rts_enabled.return_value = False
    view.manual_control_view.is_dtr_enabled.return_value = False
    view.manual_control_view.is_broadcast_enabled.return_value = False

    view.settings_save_requested = MagicMock()
    view.font_settings_changed = MagicMock()
    view.close_requested = MagicMock()
    view.preferences_requested = MagicMock()
    view.shortcut_connect_requested = MagicMock()
    view.shortcut_disconnect_requested = MagicMock()
    view.shortcut_clear_requested = MagicMock()
    view.file_transfer_dialog_opened = MagicMock()
    view.port_tab_added = MagicMock()

    view.get_port_tabs_count.return_value = 0

    # on_close_requested()가 SettingsManager.save_settings()까지 실제로 실행하므로
    # JSON 직렬화 가능한 실제 DTO를 반환해야 한다.
    view.get_window_state.return_value = MainWindowState(
        left_section_state={}, right_section_state={}
    )

    return view


@pytest.fixture
def presenter(mock_main_window, mock_settings_manager):
    """실제(임시 경로) SettingsManager를 주입한 MainPresenter 인스턴스."""
    with patch('presenter.main_presenter.SettingsManager', return_value=mock_settings_manager):
        p = MainPresenter(mock_main_window)
    yield p
    # 테스트 간 전역 싱글턴(data_logger_manager) 오염 방지
    data_logger_manager.stop_all()
    p.connection_controller.close_connection()


def _make_logging_panel(port_name: str, file_path: str) -> MagicMock:
    """`_on_logging_start_requested(panel)`이 기대하는 PortPanel Facade Mock."""
    panel = MagicMock()
    panel.get_port_name.return_value = port_name
    panel.show_save_log_dialog.return_value = file_path
    return panel


class TestShutdownStopsDataLogger:
    """앱 종료 경로(on_close_requested)가 실제로 DataLoggerManager를 정리하는지 고정."""

    def test_shutdown_stops_data_logger_and_preserves_written_bytes(
        self, presenter, loopback_config, tmp_path, qapp, qtbot
    ):
        """
        주 결함 회귀: 로깅 ON 상태로 종료해도 로거가 정리되고, Fast Path를 통해
        실제로 파일에 쓰인 바이트가 유실 없이 보존된다.
        """
        assert presenter.connection_controller.open_connection(loopback_config) is True

        file_path = tmp_path / "rx_shutdown.bin"
        panel = _make_logging_panel(LOOPBACK_PORT_NAME, str(file_path))

        presenter._on_logging_start_requested(panel)
        panel.set_logging_active.assert_any_call(True)
        assert data_logger_manager.is_logging(LOOPBACK_PORT_NAME) is True

        payload = b"HELLO-RX-SHUTDOWN"
        # 주의(S-066): `connection_controller.send_data()`는 발신(TX) 시 EventBus를
        # 거쳐 `DataTrafficHandler.on_data_sent()`로도 라우팅되어 전이중(Full Duplex)
        # 로깅상 *호출 즉시* 로거 큐에 기록된다(`test_shutdown_flushes_pending_leftover_
        # batch_before_closing_logger`의 기존 주석이 이미 문서화한 사실). LOOPBACK에서는
        # 보낸 바이트가 그대로 에코되어 RX Fast Path로도 다시 들어오므로, 그 RX 배치가
        # 셧다운 전에 추가로 flush되는지 여부(실 스레드 스케줄링에 좌우되는 경합)에 따라
        # 파일에 payload가 1회(TX만) 또는 2회(TX+RX) 기록되어 이 테스트가 간헐적으로
        # 실패했다 — 유실이 아니라 이미 존재하는 전이중 로깅 설계와 어설션 간의 불일치였다.
        # 이 테스트가 검증하려는 것은 "RX Fast Path로 들어온 데이터가 종료 후 보존되는가"
        # 하나뿐이므로, 형제 테스트와 동일하게 TX 경로를 우회하고 "외부 장치가 보낸 데이터"를
        # transport에 직접 써서 순수 RX만 재현한다.
        worker = presenter.connection_controller.workers[LOOPBACK_PORT_NAME]
        worker.transport.write(payload)

        # 실제 Fast Path(워커 스레드 에코 -> data_received -> DataTrafficHandler ->
        # data_logger_manager.write())를 통해 배경 쓰기 스레드가 큐를 완전히
        # 소비할 때까지 이벤트 루프를 돌며 기다린다 (정상 배치 타임아웃 경로).
        #
        # `dl._queue.empty()`만으로는 "아직 아무것도 도착하지 않음"과 "전부 소비됨"을
        # 구분하지 못한다 — 새로 만든 DataLogger의 큐는 시작부터 비어 있어, Fast Path가
        # 이 payload를 실어 나르기도 전에 이 조건이 우연히 참이 될 수 있다. 실제로
        # 파일에 바이트가 쓰였는지(`_file.tell()`)까지 확인해 이 거짓 양성을 차단한다.
        def _fully_written_to_logger() -> bool:
            qapp.processEvents()
            dl = data_logger_manager._loggers.get(LOOPBACK_PORT_NAME)
            return (
                dl is not None
                and dl._file is not None
                and dl._queue.empty()
                and dl._file.tell() >= len(payload)
            )

        qtbot.waitUntil(_fully_written_to_logger, timeout=2000)

        # --- 종료 경로 진입 (결함 수정 전에는 여기서 stop_all()이 호출되지 않았다) ---
        presenter.on_close_requested()

        assert data_logger_manager.is_logging(LOOPBACK_PORT_NAME) is False
        assert data_logger_manager.get_filepath(LOOPBACK_PORT_NAME) == ""
        assert presenter.connection_controller.has_active_connection is False

        assert file_path.read_bytes() == payload

    def test_shutdown_closes_pcap_with_valid_header_and_packet_structure(
        self, presenter, loopback_config, tmp_path, qapp, qtbot
    ):
        """
        PCAP 포맷도 종료 경로에서 구조가 온전하게 닫히는지 확인한다
        (S-045의 `struct.unpack` 직접 파싱 검증을 종료 경로에 대해 재사용).
        """
        import struct

        PCAP_GLOBAL_HEADER_FORMAT = "IHHIIII"
        PCAP_GLOBAL_HEADER_SIZE = struct.calcsize(PCAP_GLOBAL_HEADER_FORMAT)
        PCAP_PACKET_HEADER_FORMAT = "IIII"
        PCAP_PACKET_HEADER_SIZE = struct.calcsize(PCAP_PACKET_HEADER_FORMAT)

        assert presenter.connection_controller.open_connection(loopback_config) is True

        file_path = tmp_path / "rx_shutdown.pcap"  # .pcap 확장자 -> LogFormat.PCAP
        panel = _make_logging_panel(LOOPBACK_PORT_NAME, str(file_path))
        presenter._on_logging_start_requested(panel)
        assert data_logger_manager.is_logging(LOOPBACK_PORT_NAME) is True

        payload = b"PCAP-PAYLOAD-ON-SHUTDOWN"
        # S-066: 위 BIN 테스트와 동일한 이유(전이중 TX+RX 중복 로깅 경합, 위 주석 참조)로
        # TX 경로를 우회하고 transport에 직접 써서 순수 RX Fast Path만 재현한다.
        worker = presenter.connection_controller.workers[LOOPBACK_PORT_NAME]
        worker.transport.write(payload)

        # PCAP 글로벌 헤더 + 패킷 헤더 + payload가 모두 실제로 쓰인 뒤에만 "완료"로
        # 간주해 조기 종료(거짓 양성)를 막는다.
        expected_min_bytes = PCAP_GLOBAL_HEADER_SIZE + PCAP_PACKET_HEADER_SIZE + len(payload)

        def _fully_written_to_logger() -> bool:
            qapp.processEvents()
            dl = data_logger_manager._loggers.get(LOOPBACK_PORT_NAME)
            return (
                dl is not None
                and dl._file is not None
                and dl._queue.empty()
                and dl._file.tell() >= expected_min_bytes
            )

        qtbot.waitUntil(_fully_written_to_logger, timeout=2000)

        presenter.on_close_requested()

        assert data_logger_manager.is_logging(LOOPBACK_PORT_NAME) is False

        data = file_path.read_bytes()
        assert len(data) >= PCAP_GLOBAL_HEADER_SIZE + PCAP_PACKET_HEADER_SIZE

        magic, major, minor, thiszone, sigfigs, snaplen, network = struct.unpack(
            PCAP_GLOBAL_HEADER_FORMAT, data[:PCAP_GLOBAL_HEADER_SIZE]
        )
        assert magic == 0xA1B2C3D4
        assert major == 2
        assert minor == 4

        packet_section = data[PCAP_GLOBAL_HEADER_SIZE:]
        header_bytes = packet_section[:PCAP_PACKET_HEADER_SIZE]
        payload_bytes = packet_section[PCAP_PACKET_HEADER_SIZE:]

        ts_sec, ts_usec, incl_len, orig_len = struct.unpack(PCAP_PACKET_HEADER_FORMAT, header_bytes)
        assert incl_len == orig_len == len(payload)
        assert 0 <= ts_usec < 1_000_000
        assert payload_bytes == payload

    def test_shutdown_without_any_active_logging_does_not_raise(self, presenter):
        """로깅도 연결도 없는 상태에서 종료해도 예외 없이 통과한다."""
        assert data_logger_manager.is_logging(LOOPBACK_PORT_NAME) is False
        presenter.on_close_requested()  # 예외 없이 완료되어야 함
        assert data_logger_manager.is_logging(LOOPBACK_PORT_NAME) is False


class TestShutdownOrderingClosesConnectionBeforeLogger:
    """
    정리 순서(연결 종료 -> processEvents -> 로거 정리) 회귀.

    로거를 연결보다 먼저 닫으면, 워커 스레드가 종료 직전 `finally`에서 flush하는
    마지막 잔여 RX 배치가 이미 닫힌 파일을 향하게 되어 유실된다. 이 테스트는
    배치 임계값/타임아웃을 매우 크게 하여 "정상 배치 경로로 우연히 통과"하는
    가능성을 배제하고, 오직 종료 시 `finally`의 마지막 flush 경로만으로
    데이터가 파일에 도달하는지 확인한다.
    """

    def test_shutdown_flushes_pending_leftover_batch_before_closing_logger(
        self, presenter, loopback_config, tmp_path, qapp, qtbot, monkeypatch
    ):
        # 정상 배치 크기/시간 임계값으로는 절대 자동 flush되지 않도록 크게 키운다.
        monkeypatch.setattr("model.connection_worker.BATCH_SIZE_THRESHOLD", 10_000_000)
        monkeypatch.setattr("model.connection_worker.BATCH_TIMEOUT_MS", 10_000_000)

        assert presenter.connection_controller.open_connection(loopback_config) is True
        worker = presenter.connection_controller.workers[LOOPBACK_PORT_NAME]

        file_path = tmp_path / "rx_leftover.bin"
        panel = _make_logging_panel(LOOPBACK_PORT_NAME, str(file_path))
        presenter._on_logging_start_requested(panel)
        assert data_logger_manager.is_logging(LOOPBACK_PORT_NAME) is True

        payload = b"LEFTOVER-BATCH-ON-EXIT"
        # 주의: `connection_controller.send_data()`는 TX 발신 시 EventBus를 통해
        # `DataTrafficHandler.on_data_sent()`로도 라우팅되어 전이중(Full Duplex)
        # 로깅상 즉시 로거 큐에 기록되어 버린다 — 그러면 이 테스트가 검증하려는
        # "RX 배치가 아직 emit되지 않은 채 대기 중" 전제가 TX 쪽에서 먼저 깨진다.
        # 순수하게 RX(Fast Path)만 재현하기 위해 TX 경로를 우회하고 transport
        # 버퍼에 직접 써서 "외부 장치가 보낸 데이터"를 시뮬레이션한다.
        worker.transport.write(payload)

        # 워커 스레드가 위에서 쓴 바이트를 내부 배치 버퍼로 이미 읽어 들인 뒤일
        # 때까지 대기한다(in_waiting == 0 == transport 버퍼 소비 완료). 이 시점에는
        # 배치 임계값을 크게 키워 두었으므로 아직 emit되지 않고 배치 버퍼 안에
        # 대기 중이다 — 정상 경로로는 절대 flush되지 않는, 순수하게 종료 시
        # finally의 마지막 flush에만 의존하는 상태.
        qtbot.waitUntil(lambda: worker.transport.in_waiting == 0, timeout=2000)

        # --- 종료 경로: 이 시점에 로거로 데이터가 아직 한 바이트도 전달되지 않았다 ---
        dl_before = data_logger_manager._loggers.get(LOOPBACK_PORT_NAME)
        assert dl_before is not None and dl_before._queue.empty()

        presenter.on_close_requested()

        assert data_logger_manager.is_logging(LOOPBACK_PORT_NAME) is False
        assert file_path.read_bytes() == payload, (
            "워커 종료 직전 finally에서 flush된 마지막 배치가 로거가 닫히기 전에 "
            "파일에 도달하지 못했다 (정리 순서 회귀)"
        )
