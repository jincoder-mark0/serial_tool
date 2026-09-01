"""
포트/시스템 로그 생명주기 조정자.

DataLoggerManager 제어, 저장 경로 선택, 시스템 로그 TextLogWriter 생명주기를 한 곳에서
관리합니다. 상위 계층에 로그 메시지를 전달할 때 callback을 주입받지 않고 Qt signal을
발행하므로 composition root에서 독립적으로 생성할 수 있습니다.
"""
from typing import Optional
from weakref import WeakSet

from PyQt5.QtCore import QObject, pyqtSignal

from core.data_logger import DataLoggerManager
from core.text_log_writer import TextLogWriter
from presenter.logging_format_resolver import LoggingFormatResolver
from view.panels.port_panel import PortPanel
from view.sections.main_left_section import MainLeftSection


class LoggingCoordinator(QObject):
    """포트 데이터 로그와 시스템 로그 REC의 UI/저장 흐름을 관리합니다."""

    info_requested = pyqtSignal(str)
    error_requested = pyqtSignal(str)

    def __init__(
        self,
        port_view: MainLeftSection,
        data_logger_manager: DataLoggerManager,
    ) -> None:
        super().__init__()
        self._port_view = port_view
        self._data_logger_manager = data_logger_manager
        self._system_log_writer: Optional[TextLogWriter] = None
        self._connected_panels: WeakSet[PortPanel] = WeakSet()
        self._system_signals_connected = False

    @property
    def system_log_writer(self) -> Optional[TextLogWriter]:
        """진단/테스트용 현재 시스템 로그 writer를 반환합니다."""
        return self._system_log_writer

    def connect_signals(self) -> None:
        """기존/신규 포트 패널과 시스템 로그 recording signal을 연결합니다."""
        for panel in self._port_view.get_port_panels():
            self.connect_port_panel(panel)

        if self._system_signals_connected:
            return

        self._port_view.port_tab_added.connect(self.on_port_tab_added)
        self._port_view.sys_logging_start_requested.connect(
            self.on_system_logging_start_requested
        )
        self._port_view.sys_logging_stop_requested.connect(
            self.on_system_logging_stop_requested
        )
        self._port_view.system_log_line_appended.connect(
            self.on_system_log_line_appended
        )
        self._system_signals_connected = True

    def on_port_tab_added(self, panel: PortPanel) -> None:
        """새 PortPanel의 logging 요청을 coordinator에 연결합니다."""
        self.connect_port_panel(panel)

    def connect_port_panel(self, panel: PortPanel) -> None:
        """단일 PortPanel의 기록 시작/중지 요청을 중복 없이 연결합니다."""
        if not hasattr(panel, "logging_start_requested"):
            return
        if panel in self._connected_panels:
            return

        panel.logging_start_requested.connect(
            lambda p=panel: self.on_port_logging_start_requested(p)
        )
        panel.logging_stop_requested.connect(
            lambda p=panel: self.on_port_logging_stop_requested(p)
        )
        self._connected_panels.add(panel)

    @staticmethod
    def _choose_log_path(widget) -> Optional[str]:
        """View facade의 저장 대화상자를 열고 취소 시 REC 상태를 원복합니다."""
        file_path = widget.show_save_log_dialog()
        if not file_path:
            widget.set_logging_active(False)
            return None
        return file_path

    def on_port_logging_start_requested(self, panel: PortPanel) -> None:
        """포트 데이터 로그 기록을 시작합니다."""
        file_path = self._choose_log_path(panel)
        if file_path is None:
            return

        port = panel.get_port_name()
        if not port:
            panel.set_logging_active(False)
            return

        log_format = LoggingFormatResolver.resolve(file_path)
        if self._data_logger_manager.start_logging(port, file_path, log_format):
            panel.set_logging_active(True)
            self.info_requested.emit(
                f"[{port}] Logging started ({log_format.value}): {file_path}"
            )
            return

        panel.set_logging_active(False)
        self.error_requested.emit(f"[{port}] Failed to start logging")

    def on_port_logging_stop_requested(self, panel: PortPanel) -> None:
        """포트 데이터 로그 기록을 중지합니다."""
        port = panel.get_port_name()
        if port:
            self._data_logger_manager.stop_logging(port)
        panel.set_logging_active(False)
        self.info_requested.emit(f"[{port}] Logging stopped")

    def on_system_logging_start_requested(self) -> None:
        """시스템 로그 텍스트 기록을 시작합니다."""
        file_path = self._choose_log_path(self._port_view)
        if file_path is None:
            return

        writer = TextLogWriter()
        try:
            writer.open(file_path)
        except OSError as exc:
            self._port_view.set_logging_active(False)
            self.error_requested.emit(
                f"Failed to start system log recording ({file_path}): {exc}"
            )
            return

        self.close_system_log()
        self._system_log_writer = writer
        self._port_view.set_logging_active(True)
        self.info_requested.emit(f"System log recording enabled: {file_path}")

    def on_system_logging_stop_requested(self) -> None:
        """시스템 로그 텍스트 기록을 중지합니다."""
        self.close_system_log()
        self._port_view.set_logging_active(False)
        self.info_requested.emit("System log recording stopped")

    def close_system_log(self) -> None:
        """열린 시스템 로그 writer를 idempotent하게 닫습니다."""
        if self._system_log_writer is None:
            return
        self._system_log_writer.close()
        self._system_log_writer = None

    def on_system_log_line_appended(self, text: str) -> None:
        """화면에 추가된 시스템 로그 한 줄을 활성 writer에 기록합니다."""
        writer = self._system_log_writer
        if writer is None:
            return

        try:
            writer.write_line(text)
        except OSError as exc:
            self._system_log_writer = None
            writer.close()
            self._port_view.set_logging_active(False)
            self.error_requested.emit(
                f"System log write failed, recording stopped: {exc}"
            )
