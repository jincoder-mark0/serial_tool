"""
S-059 회귀 테스트: 앱 종료 시 RX 데이터 로거 미정리 결함

## WHY
* `core/data_logger.py`의 `DataLoggerManager.stop_all()`이 저장소 어디에서도
  호출되지 않았다. 로깅을 켠 채 앱을 종료하면 데몬 쓰기 스레드가 프로세스
  종료와 함께 강제로 죽어 큐에 남은 데이터가 유실되고 파일이 정상적으로 닫히지 않는다.
* `stop_logging(port)` 단위 테스트로는 호출 자체가 없는 결함을 잡을 수 없으므로
  `MainPresenter.on_close_requested()`라는 실제 종료 경로를 태운다.
* 정리 순서는 connection close -> queued signal delivery -> logger stop 이어야 한다.

## HOW
* View는 MagicMock, SettingsManager는 임시 경로 fixture를 사용한다.
* Production과 동일하게 ApplicationBootstrapper가 MainPresenter까지 생성한다.
* LOOPBACK_PORT_NAME을 사용해 실제 QThread 기반 ConnectionWorker를 구동한다.
"""
from unittest.mock import MagicMock

import pytest

from application_bootstrap import ApplicationBootstrapper
from common.constants import LOOPBACK_PORT_NAME
from common.dtos import MainWindowState, PortConfig
from common.enums import SerialFlowControl, SerialParity, SerialStopBits
from core.data_logger import data_logger_manager


@pytest.fixture
def loopback_config() -> PortConfig:
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
    view.manual_control_view.is_auto_tx_enabled.return_value = False
    view.manual_control_view.get_auto_tx_interval_ms.return_value = 1000

    view.settings_save_requested = MagicMock()
    view.font_settings_changed = MagicMock()
    view.theme_change_requested = MagicMock()
    view.language_change_requested = MagicMock()
    view.close_requested = MagicMock()
    view.preferences_requested = MagicMock()
    view.shortcut_connect_requested = MagicMock()
    view.shortcut_disconnect_requested = MagicMock()
    view.shortcut_clear_requested = MagicMock()
    view.file_transfer_dialog_opened = MagicMock()
    view.get_window_state.return_value = MainWindowState(
        left_section_state={}, right_section_state={}
    )
    return view


@pytest.fixture
def presenter(mock_main_window, mock_settings_manager):
    runtime = ApplicationBootstrapper(
        mock_main_window,
        mock_settings_manager,
    ).build()
    yield runtime.main_presenter
    data_logger_manager.stop_all()
    runtime.status_coordinator.stop()
    runtime.file_transfer_manager.shutdown()
    runtime.macro_script_manager.stop()
    runtime.port_scan_manager.stop()
    runtime.connection_controller.close_connection()


def _make_logging_panel(port_name: str, file_path: str) -> MagicMock:
    panel = MagicMock()
    panel.get_port_name.return_value = port_name
    panel.show_save_log_dialog.return_value = file_path
    return panel


class TestShutdownStopsDataLogger:
    def test_shutdown_stops_data_logger_and_preserves_written_bytes(
        self, presenter, loopback_config, tmp_path, qapp, qtbot
    ):
        assert presenter.connection_controller.open_connection(loopback_config) is True

        file_path = tmp_path / "rx_shutdown.bin"
        panel = _make_logging_panel(LOOPBACK_PORT_NAME, str(file_path))
        presenter.logging_coordinator.on_port_logging_start_requested(panel)
        panel.set_logging_active.assert_any_call(True)
        assert data_logger_manager.is_logging(LOOPBACK_PORT_NAME) is True

        payload = b"HELLO-RX-SHUTDOWN"
        worker = presenter.connection_controller.workers[LOOPBACK_PORT_NAME]
        worker.transport.write(payload)

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
        presenter.on_close_requested()

        assert data_logger_manager.is_logging(LOOPBACK_PORT_NAME) is False
        assert data_logger_manager.get_filepath(LOOPBACK_PORT_NAME) == ""
        assert presenter.connection_controller.has_active_connection is False
        assert file_path.read_bytes() == payload

    def test_shutdown_closes_pcap_with_valid_header_and_packet_structure(
        self, presenter, loopback_config, tmp_path, qapp, qtbot
    ):
        import struct

        global_header_format = "IHHIIII"
        global_header_size = struct.calcsize(global_header_format)
        packet_header_format = "IIII"
        packet_header_size = struct.calcsize(packet_header_format)

        assert presenter.connection_controller.open_connection(loopback_config) is True

        file_path = tmp_path / "rx_shutdown.pcap"
        panel = _make_logging_panel(LOOPBACK_PORT_NAME, str(file_path))
        presenter.logging_coordinator.on_port_logging_start_requested(panel)
        assert data_logger_manager.is_logging(LOOPBACK_PORT_NAME) is True

        payload = b"PCAP-PAYLOAD-ON-SHUTDOWN"
        worker = presenter.connection_controller.workers[LOOPBACK_PORT_NAME]
        worker.transport.write(payload)
        expected_min_bytes = global_header_size + packet_header_size + len(payload)

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
        assert len(data) >= global_header_size + packet_header_size
        magic, major, minor, _thiszone, _sigfigs, _snaplen, _network = struct.unpack(
            global_header_format, data[:global_header_size]
        )
        assert magic == 0xA1B2C3D4
        assert major == 2
        assert minor == 4

        packet_section = data[global_header_size:]
        header_bytes = packet_section[:packet_header_size]
        payload_bytes = packet_section[packet_header_size:]
        _ts_sec, ts_usec, incl_len, orig_len = struct.unpack(
            packet_header_format, header_bytes
        )
        assert incl_len == orig_len == len(payload)
        assert 0 <= ts_usec < 1_000_000
        assert payload_bytes == payload

    def test_shutdown_without_any_active_logging_does_not_raise(self, presenter):
        assert data_logger_manager.is_logging(LOOPBACK_PORT_NAME) is False
        presenter.on_close_requested()
        assert data_logger_manager.is_logging(LOOPBACK_PORT_NAME) is False


class TestShutdownOrderingClosesConnectionBeforeLogger:
    def test_shutdown_flushes_pending_leftover_batch_before_closing_logger(
        self, presenter, loopback_config, tmp_path, qapp, qtbot, monkeypatch
    ):
        monkeypatch.setattr("model.connection_worker.BATCH_SIZE_THRESHOLD", 10_000_000)
        monkeypatch.setattr("model.connection_worker.BATCH_TIMEOUT_MS", 10_000_000)

        assert presenter.connection_controller.open_connection(loopback_config) is True
        worker = presenter.connection_controller.workers[LOOPBACK_PORT_NAME]

        file_path = tmp_path / "rx_leftover.bin"
        panel = _make_logging_panel(LOOPBACK_PORT_NAME, str(file_path))
        presenter.logging_coordinator.on_port_logging_start_requested(panel)
        assert data_logger_manager.is_logging(LOOPBACK_PORT_NAME) is True

        payload = b"LEFTOVER-BATCH-ON-EXIT"
        worker.transport.write(payload)
        qtbot.waitUntil(lambda: worker.transport.in_waiting == 0, timeout=2000)

        dl_before = data_logger_manager._loggers.get(LOOPBACK_PORT_NAME)
        assert dl_before is not None and dl_before._queue.empty()

        presenter.on_close_requested()

        assert data_logger_manager.is_logging(LOOPBACK_PORT_NAME) is False
        assert file_path.read_bytes() == payload, (
            "워커 종료 직전 flush된 마지막 배치가 logger close 전에 파일에 도달하지 못했다"
        )
