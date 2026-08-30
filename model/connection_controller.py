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
            worker = self.session_factory.create_worker(config)
        except (ValueError, OSError) as exc:
            self.packet_parser_manager.remove(name)
            self._emit_error(name, f"Invalid connection configuration: {exc}")
            return False

        self.connection_configs[name] = config
        worker.connection_opened.connect(
            lambda n=name: self.connection_opened.emit(
                PortConnectionEvent(
                    port=n,
                    state=ConnectionEventState.OPENED.value,
                )
            )
        )
        worker.connection_closed.connect(self.on_worker_closed)
        worker.worker_terminated.connect(self.on_worker_terminated)
        worker.error_occurred.connect(lambda msg, n=name: self._emit_error(n, msg))
        worker.data_received.connect(
            lambda data, n=name: self._handle_data_received(n, data)
        )

        self.workers[name] = worker
        worker.start()
        return True

    def close_connection(self, name: Optional[str] = None) -> None:
        if name:
            worker = self.workers.get(name)
            if worker:
                worker.stop()
                self.on_worker_closed(name)
            return

        for port_name in list(self.workers.keys()):
            self.close_connection(port_name)

    def _cleanup_worker_registry(self, name: str) -> bool:
        was_registered = name in self.workers
        self.workers.pop(name, None)

        for packet in self.packet_parser_manager.remove(name):
            self.packet_received.emit(PacketEvent(port=name, packet=packet))

        self.connection_configs.pop(name, None)
        return was_registered

    def on_worker_closed(self, name: str) -> None:
        if self._cleanup_worker_registry(name):
            self.connection_closed.emit(
                PortConnectionEvent(
                    port=name,
                    state=ConnectionEventState.CLOSED.value,
                )
            )

    def on_worker_terminated(self, name: str) -> None:
        self._cleanup_worker_registry(name)

    def _emit_error(self, port: str, message: str) -> None:
        self.error_occurred.emit(PortErrorEvent(port=port, message=message))

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
