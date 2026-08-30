"""
연결 컨트롤러 모듈

개별 연결 세션의 생명주기, Parser, Worker 및 데이터 흐름을 관리합니다.
계층 간 이벤트는 DTO로 전달하며 연결 상태 문자열은 common enum을 정본으로 사용합니다.
"""
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from PyQt5.QtCore import QObject, pyqtSignal

from common.constants import EventTopics, LOOPBACK_PORT_NAME
from common.dtos import PacketEvent, PortConfig, PortConnectionEvent, PortDataEvent, PortErrorEvent
from common.enums import ConnectionEventState, ConnectionProtocol, ParserType
from core.event_bus import event_bus
from core.logger import logger
from core.transport.loopback_transport import LoopbackTransport
from core.transport.serial_transport import SerialTransport
from model.connection_worker import ConnectionWorker
from model.packet_parser import PacketParser, ParserFactory

if TYPE_CHECKING:
    from model.file_transfer_service import FileTransferService


class ConnectionController(QObject):
    """다중 연결의 Worker/Parser/설정과 송수신 요청을 관리합니다."""

    connection_opened = pyqtSignal(object)
    connection_closed = pyqtSignal(object)
    error_occurred = pyqtSignal(object)
    data_received = pyqtSignal(object)
    data_sent = pyqtSignal(object)
    packet_received = pyqtSignal(object)

    def __init__(self) -> None:
        super().__init__()
        self.workers: Dict[str, ConnectionWorker] = {}
        self.parsers: Dict[str, PacketParser] = {}
        self.connection_configs: Dict[str, PortConfig] = {}
        self._active_file_transfers: Dict[str, "FileTransferService"] = {}
        self.event_bus = event_bus
        self._connect_signals_to_eventbus()

    def _connect_signals_to_eventbus(self) -> None:
        self.connection_opened.connect(lambda e: self.event_bus.publish(EventTopics.PORT_OPENED, e))
        self.connection_closed.connect(lambda e: self.event_bus.publish(EventTopics.PORT_CLOSED, e))
        self.error_occurred.connect(lambda e: self.event_bus.publish(EventTopics.PORT_ERROR, e))
        self.data_received.connect(lambda e: self.event_bus.publish(EventTopics.PORT_DATA_RECEIVED, e))
        self.data_sent.connect(lambda e: self.event_bus.publish(EventTopics.PORT_DATA_SENT, e))
        self.packet_received.connect(lambda e: self.event_bus.publish(EventTopics.PORT_PACKET_RECEIVED, e))

    def register_file_transfer(self, port_name: str, file_transfer_service: "FileTransferService") -> None:
        self._active_file_transfers[port_name] = file_transfer_service
        logger.debug(f"File transfer registered for port {port_name}")

    def unregister_file_transfer(self, port_name: str) -> None:
        if port_name in self._active_file_transfers:
            del self._active_file_transfers[port_name]
            logger.debug(f"File transfer unregistered for port {port_name}")

    @property
    def has_active_connection(self) -> bool:
        return bool(self.workers)

    def has_active_broadcast_ports(self) -> bool:
        return any(worker.isRunning() and worker.broadcast_enabled() for worker in self.workers.values())

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

        transport = LoopbackTransport(config) if name == LOOPBACK_PORT_NAME else SerialTransport(config)
        worker = ConnectionWorker(transport, name)

        parser_type = ParserType.from_preference_index(config.parser_type)
        try:
            parser_kwargs = self._build_parser_kwargs(parser_type, config)
            self.parsers[name] = ParserFactory.create_parser(parser_type, **parser_kwargs)
        except ValueError as exc:
            self._emit_error(name, f"Invalid packet parser configuration: {exc}")
            return False

        self.connection_configs[name] = config
        worker.connection_opened.connect(
            lambda n=name: self.connection_opened.emit(
                PortConnectionEvent(port=n, state=ConnectionEventState.OPENED.value)
            )
        )
        worker.connection_closed.connect(self.on_worker_closed)
        worker.worker_terminated.connect(self.on_worker_terminated)
        worker.error_occurred.connect(lambda msg, n=name: self._emit_error(n, msg))
        worker.data_received.connect(lambda data, n=name: self._handle_data_received(n, data))

        self.workers[name] = worker
        worker.start()
        return True

    def close_connection(self, name: Optional[str] = None) -> None:
        if name:
            transfer_engine = self._active_file_transfers.get(name)
            if transfer_engine:
                logger.warning(f"Closing port {name} while file transfer is active. Cancelling transfer...")
                transfer_engine.cancel()

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

        parser = self.parsers.get(name)
        if parser:
            for packet in parser.flush():
                self.packet_received.emit(PacketEvent(port=name, packet=packet))
            self.parsers.pop(name, None)

        self.connection_configs.pop(name, None)
        return was_registered

    def on_worker_closed(self, name: str) -> None:
        if self._cleanup_worker_registry(name):
            self.connection_closed.emit(
                PortConnectionEvent(port=name, state=ConnectionEventState.CLOSED.value)
            )

    def on_worker_terminated(self, name: str) -> None:
        self._cleanup_worker_registry(name)

    @staticmethod
    def _build_parser_kwargs(parser_type: str, config: PortConfig) -> Dict[str, Any]:
        if parser_type == ParserType.DELIMITER:
            return {"delimiter": ConnectionController._decode_delimiter(config.packet_delimiter)}
        if parser_type == ParserType.FIXED_LENGTH:
            return {"length": config.packet_length}
        if parser_type == ParserType.LENGTH_FIELD:
            return {
                "length_field_offset": config.length_field_offset,
                "length_field_size": config.length_field_size,
                "length_field_endian": config.length_field_endian,
                "length_includes_header": config.length_includes_header,
            }
        if parser_type == ParserType.GAP:
            return {"gap_ms": config.gap_ms}
        return {}

    @staticmethod
    def _decode_delimiter(raw: str) -> bytes:
        if not raw:
            return b""
        try:
            return raw.encode("utf-8").decode("unicode_escape").encode("latin-1")
        except (UnicodeDecodeError, UnicodeEncodeError):
            return raw.encode("utf-8")

    def _emit_error(self, port: str, message: str) -> None:
        self.error_occurred.emit(PortErrorEvent(port=port, message=message))

    def _handle_data_received(self, name: str, data: bytes) -> None:
        self.data_received.emit(PortDataEvent(port=name, data=data))
        parser = self.parsers.get(name)
        if parser:
            for packet in parser.parse(data):
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
            logger.warning(f"Broadcast failed on {len(failed)}/{targets} port(s): {failed}")
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
            logger.warning(f"Send-to-all failed on {len(failed)}/{targets} port(s): {failed}")
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
