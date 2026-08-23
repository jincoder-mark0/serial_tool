"""
PortScanWorker 종료 시 미정리 결함 회귀 테스트 모듈 (S-062)

## WHY
* `doc/refactor_audit_20260822.md`(S-059 조사에서 발견): 종료 시퀀스가 정리하는
  자원 목록에 `model/port_scanner.py`의 스캔 스레드가 없었다. 온디맨드 초단명
  스레드이고 파일·데이터 핸들이 없어 최악이 스레드 leak 수준이지만, 종료 중
  스캔이 겹치면 QThread가 실행 중인 채로 파괴되어 Qt 경고("QThread: Destroyed
  while thread is still running")나 드문 크래시로 이어질 수 있다.
* 데이터 유실과 무관한 스레드이므로 정리 위치는 RX 로거의 "연결 종료 ->
  processEvents -> 로거 정리" 순서(S-059)와 무관하게 안전하다 — 이 테스트는
  ①실제로 스레드가 정리되는지, ②`MainPresenter.on_close_requested()`가 실제로
  그 정리 지점을 호출하는지 고정한다.

## WHAT
* `PortPresenter.stop_pending_scan()`: 스캔이 진행 중일 때/없을 때 모두 예외
  없이 정리되는지 (실제 QThread, Mock 아님).
* `MainPresenter.on_close_requested()`: 종료 경로가 실제로
  `port_presenter.stop_pending_scan()`을 호출하는지.

## HOW
* `tests/test_port_tab_cleanup.py`와 동일한 패턴 — 실제 MainLeftSection +
  PortPresenter + ConnectionController를 조립해 실제 QThread 기반 스캔을
  구동한다. 스캔과 종료 정리가 실제로 겹치도록
  `serial.tools.list_ports.comports`를 지연시켜 결정론적으로 재현한다.
* `MainPresenter` 배선 확인은 `tests/test_shutdown_data_logger.py`와 동일한
  Mock View 패턴을 재사용한다(파일 간 fixture 공유 없이 로컬 정의 — 기존 관례).
"""
import time
from unittest.mock import MagicMock, patch

import pytest

from common.dtos import MainWindowState
from model.connection_controller import ConnectionController
from presenter.port_presenter import PortPresenter
from presenter.main_presenter import MainPresenter
from view.sections.main_left_section import MainLeftSection
from view.panels.packet_panel import PacketPanel
from view.panels.manual_control_panel import ManualControlPanel
from view.widgets.system_log import SystemLogWidget


# -----------------------------------------------------------------------------
# 1. PortPresenter.stop_pending_scan() — 실제 QThread
# -----------------------------------------------------------------------------

@pytest.fixture
def wired_presenter(qapp):
    """실제 MainLeftSection + PortPresenter + ConnectionController 조립체
    (tests/test_port_tab_cleanup.py와 동일한 패턴)."""
    left_section = MainLeftSection()
    controller = ConnectionController()
    presenter = PortPresenter(left_section, controller)
    try:
        yield left_section, presenter, controller
    finally:
        controller.close_connection()


class TestStopPendingScan:
    """진행 중인 스캔 스레드가 종료 정리 호출로 실제로 정리되는지 고정."""

    def test_stop_pending_scan_waits_for_running_scan_without_raising(self, wired_presenter):
        """
        스캔이 아직 끝나지 않은 상태(종료와 스캔이 겹친 상황)에서 정리를
        호출해도 예외 없이 반환되고, 스레드가 실행 중인 채로 방치되지 않는다.
        """
        _left_section, presenter, _controller = wired_presenter

        def _slow_comports():
            time.sleep(0.2)
            return []

        with patch(
            "model.port_scanner.serial.tools.list_ports.comports",
            side_effect=_slow_comports,
        ):
            presenter.scan_ports()
            worker = presenter._scan_worker
            assert worker is not None
            assert worker.isRunning() is True  # 아직 스캔 진행 중 — 종료와 겹친 상황 재현

            # WHEN: 앱 종료 정리 호출 (예외가 나면 이 테스트가 실패한다)
            presenter.stop_pending_scan()

        # THEN: 스레드가 완전히 끝난 뒤에야 반환되었고, 참조도 해제되었다
        assert worker.isRunning() is False
        assert presenter._scan_worker is None

    def test_stop_pending_scan_without_any_scan_does_not_raise(self, wired_presenter):
        """스캔이 실행된 적이 없어도 예외 없이 통과한다."""
        _left_section, presenter, _controller = wired_presenter

        presenter.stop_pending_scan()

        assert presenter._scan_worker is None

    def test_stop_pending_scan_after_scan_already_finished_does_not_raise(
        self, wired_presenter, qapp, qtbot
    ):
        """스캔이 이미 끝난 뒤(정상 경로)에 호출해도 예외 없이 통과한다."""
        _left_section, presenter, _controller = wired_presenter

        presenter.scan_ports()
        qtbot.waitUntil(lambda: presenter._scan_worker is None, timeout=2000)

        presenter.stop_pending_scan()  # 예외 없이 완료되어야 함

        assert presenter._scan_worker is None


# -----------------------------------------------------------------------------
# 2. MainPresenter.on_close_requested() — 실제 종료 경로 배선 확인
# -----------------------------------------------------------------------------

@pytest.fixture
def mock_main_window():
    """MainPresenter 초기화에 필요한 최소 MainWindow Mock
    (tests/test_shutdown_data_logger.py의 fixture와 동일한 패턴)."""
    view = MagicMock()

    view.left_section = MagicMock()
    view.right_section = MagicMock()
    view.left_section.port_tab_panel = MagicMock()
    view.left_section.port_tab_panel.currentIndex.return_value = 0
    view.left_section.port_tab_panel.widget.return_value = MagicMock()
    view.left_section.manual_control_panel = MagicMock(spec=ManualControlPanel)
    view.left_section.system_log_widget = MagicMock(spec=SystemLogWidget)
    view.right_section.packet_panel = MagicMock(spec=PacketPanel)
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
    p.connection_controller.close_connection()


class TestMainPresenterShutdownStopsPendingScan:
    """on_close_requested()가 실제로 PortPresenter.stop_pending_scan()을 호출하는지 고정."""

    def test_shutdown_calls_stop_pending_scan(self, presenter):
        with patch.object(
            presenter.port_presenter, "stop_pending_scan"
        ) as mock_stop:
            presenter.on_close_requested()

        mock_stop.assert_called_once()

    def test_shutdown_without_pending_scan_does_not_raise(self, presenter):
        """스캔이 없는 평상시 종료도 예외 없이 통과한다(회귀 방지)."""
        presenter.on_close_requested()  # 예외 없이 완료되어야 함
