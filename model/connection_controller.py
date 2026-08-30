"""
연결 컨트롤러 모듈.

다중 연결 worker 생명주기/registry와 송수신 요청을 관리합니다. 구체 Transport/Worker
생성은 ConnectionSessionFactory, packet parser 세션은 PacketParserManager에 위임합니다.
"""
from typing import Dict, List, Optional

from PyQt5.QtCore import QObject, pyqtSignal

from common.dtos import PacketEvent, PortConfig, PortConnectionEvent, PortDataEvent, PortErrorEvent
from common.enums import ConnectionEventState, ConnectionProtocol
from core.logger import logger
from model.connection_session_factory import ConnectionSessionFactory
from model.connection_worker import ConnectionWorker
from model.packet_parser_manager import PacketParserManager


class ConnectionController(QObject):
    """다중 연결 세션의 worker/configuration과 송수신을 관리합니다."""

    connection_opened = pyqtSignal(object)
    # 기능별 manager가 worker stop 전에 자기 작업을 취소할 수 있는 중립 lifecycle signal.
    connection_closing = pyqtSignal(str)
    connection_closed = pyqtSignal(object)
    error_occurred = pyqtSignal(object)
    data_received = pyqtSignal(object)
    data_sent = pyqtSignal(object)
    packet_received = pyqtSignal(object)

    def __init__(
        self,
        packet_parser_manager: Optional[PacketParserManager] = None,
        session_factory: Optional[ConnectionSessionFactory] = None,
    ) -> None:
        super().__init__()
        self.workers: Dict[str, ConnectionWorker] = {}
        self.connection_configs: Dict[str, PortConfig] = {}
        self._retired_workers: Dict[str, ConnectionWorker] = {}
        self.packet_parser_manager = packet_parser_manager or PacketParserManager()
        self.session_factory = session_factory or ConnectionSessionFactory()

    @property
    def has_active_connection(self) -> bool:
        return bool(self.workers)

    def has_active_broadcast_ports(self) -> bool:
        return any(
            worker.isRunning() and worker.broadcast_enabled()
            for worker in self.workers.values()
        )

    def get_active_connections(self) -> List[str]:
        return list(self.workers.keys())

    def is_connection_open(self, name: str) -> bool:
        worker = self.workers.get(name)
        return worker is not None and worker.isRunning()

    def get_connection_config(self, name: str) -> Optional[PortConfig]:
        return self.connection_configs.get(name)

    def get_write_queue_size(self, name: str) -> int:
        worker = self.workers.get(name)
        return worker.get_write_queue_size() if worker else 0

    def is_write_idle(self, name: str) -> bool:
        """대상 Worker의 Queue와 in-flight transport write가 모두 끝났는지 확인합니다."""
        worker = self.workers.get(name)
        return worker is not None and worker.is_write_idle()

    def get_write_error(self, name: str) -> Optional[str]:
        """대상 Worker의 terminal transport write 오류를 반환합니다."""
        worker = self.workers.get(name)
        return worker.get_write_error() if worker else None

    def open_connection(self, config: PortConfig) -> bool:
        name = config.port
        if not name:
            self._emit_error("", "Connection name(port) is required.")
            return False
        if self.is_connection_open(name):
            self._emit_error(name, "Connection is already open.")
            return False
        if config.protocol not in ConnectionProtocol.SUPPORTED:
            self._emit_error(
                name,
                f"Protocol '{config.protocol}' is not implemented yet. Connection not attempted.",
            )
            return False

        try:
            self.packet_parser_manager.configure(name, config)
        except (TypeError, ValueError) as exc:
            self._emit_error(name, f"Invalid packet parser configuration: {exc}")
            return False

        try:
            worker = self.session_factory.create_worker(config)
        except (ValueError, OSError) as exc:
            self.packet_parser_manager.remove(name)
            self._emit_error(name, f"Failed to create connection session: {exc}")
            return False

        self.connection_configs[name] = config
        worker.connection_opened.connect(
            lambda _name, n=name, w=worker: self._on_worker_opened(n, w)
        )
        worker.connection_closed.connect(
            lambda _name, n=name, w=worker: self.on_worker_closed(n, w)
        )
        worker.worker_terminated.connect(
            lambda _name, n=name, w=worker: self.on_worker_terminated(n, w)
        )
        worker.error_occurred.connect(
            lambda msg, n=name, w=worker: self._on_worker_error(n, w, msg)
        )
        worker.data_received.connect(
            lambda data, n=name, w=worker: self._on_worker_data_received(n, w, data)
        )

        self.workers[name] = worker
        worker.start()
        return True

    def close_connection(self, name: Optional[str] = None) -> None:
        if name:
            worker = self.workers.get(name)
            if worker:
                self.connection_closing.emit(name)
                worker.stop()
                # worker의 cross-thread connection_closed는 main event loop에 queued될 수
                # 있으므로 registry는 stop() 반환 직후 동기적으로도 정리합니다.
                self.on_worker_closed(name, worker)
            return

        for port_name in list(self.workers.keys()):
            self.close_connection(port_name)

    def _cleanup_worker_registry(
        self,
        name: str,
        expected_worker: Optional[ConnectionWorker] = None,
    ) -> bool:
        current_worker = self.workers.get(name)
        if current_worker is None:
            return False
        if expected_worker is not None and current_worker is not expected_worker:
            return False

        was_registered = True
        self._retired_workers[name] = current_worker
        self.workers.pop(name, None)

        for packet in self.packet_parser_manager.remove(name):
            self.packet_received.emit(PacketEvent(port=name, packet=packet))

        self.connection_configs.pop(name, None)
        return was_registered

    def on_worker_closed(
        self,
        name: str,
        worker: Optional[ConnectionWorker] = None,
    ) -> None:
        if self._cleanup_worker_registry(name, worker):
            self.connection_closed.emit(
                PortConnectionEvent(
                    port=name,
                    state=ConnectionEventState.CLOSED.value,
                )
            )

    def on_worker_terminated(
        self,
        name: str,
        worker: Optional[ConnectionWorker] = None,
    ) -> None:
        self._cleanup_worker_registry(name, worker)
        if self._retired_workers.get(name) is worker:
            self._retired_workers.pop(name, None)

    def _emit_error(self, port: str, message: str) -> None:
        self.error_occurred.emit(PortErrorEvent(port=port, message=message))

    def _is_current_worker(self, name: str, worker: ConnectionWorker) -> bool:
        """Queued signal의 발신 Worker가 현재 port session인지 확인합니다."""
        return self.workers.get(name) is worker

    def _is_current_or_retiring_worker(
        self,
        name: str,
        worker: ConnectionWorker,
    ) -> bool:
        """새 세션이 없을 때 retiring Worker의 final data/error만 허용합니다."""
        current_worker = self.workers.get(name)
        if current_worker is worker:
            return True
        return (
            current_worker is None
            and self._retired_workers.get(name) is worker
        )

    def _on_worker_opened(self, name: str, worker: ConnectionWorker) -> None:
        if not self._is_current_worker(name, worker):
            return
        self.connection_opened.emit(
            PortConnectionEvent(
                port=name,
                state=ConnectionEventState.OPENED.value,
            )
        )

    def _on_worker_error(
        self,
        name: str,
        worker: ConnectionWorker,
        message: str,
    ) -> None:
        if not self._is_current_or_retiring_worker(name, worker):
            return
        self._emit_error(name, message)

    def _on_worker_data_received(
        self,
        name: str,
        worker: ConnectionWorker,
        data: bytes,
    ) -> None:
        if not self._is_current_or_retiring_worker(name, worker):
            return
        self._handle_data_received(name, data)

    def _handle_data_received(self, name: str, data: bytes) -> None:
        self.data_received.emit(PortDataEvent(port=name, data=data))

        for packet in self.packet_parser_manager.feed(name, data):
            self.packet_received.emit(PacketEvent(port=name, packet=packet))

    def send_data(self, port_name: str, data: bytes) -> bool:
        if not port_name:
            self._emit_error("", "Cannot send data: Port name is not specified.")
            return False
        if not self.is_connection_open(port_name):
            self._emit_error(port_name, "Cannot send data: Port is not open.")
            return False
        return self.send_data_to_connection(port_name, data)

    def send_broadcast_data(self, data: bytes) -> bool:
        if not self.workers:
            self._emit_error("", "No active connections.")
            return False

        targets = 0
        failed = []
        for name, worker in list(self.workers.items()):
            if worker.isRunning() and worker.broadcast_enabled():
                targets += 1
                if not self.send_data_to_connection(name, data):
                    failed.append(name)

        if targets == 0:
            logger.warning("No active connections enabled for broadcasting.")
            return False
        if failed:
            logger.warning(
                f"Broadcast failed on {len(failed)}/{targets} port(s): {failed}"
            )
            return False
        return True

    def send_data_to_all(self, data: bytes) -> bool:
        if not self.workers:
            self._emit_error("", "No active connections.")
            return False

        targets = 0
        failed = []
        for name, worker in list(self.workers.items()):
            if worker.isRunning():
                targets += 1
                if not self.send_data_to_connection(name, data):
                    failed.append(name)

        if failed:
            logger.warning(
                f"Send-to-all failed on {len(failed)}/{targets} port(s): {failed}"
            )
        return targets > 0 and not failed

    def send_data_to_connection(self, name: str, data: bytes) -> bool:
        worker = self.workers.get(name)
        if worker and worker.isRunning() and worker.send_data(data):
            self.data_sent.emit(PortDataEvent(port=name, data=data))
            return True
        return False

    def set_port_broadcast_state(self, port_name: str, state: bool) -> None:
        worker = self.workers.get(port_name)
        if worker:
            worker.set_broadcast(state)

    def set_dtr(self, state: bool) -> None:
        for worker in self.workers.values():
            worker.set_dtr(state)

    def set_rts(self, state: bool) -> None:
        for worker in self.workers.values():
            worker.set_rts(state)

    def set_broadcast(self, state: bool) -> None:
        for worker in self.workers.values():
            worker.set_broadcast(state)
