"""
연결 컨트롤러 모듈.

다중 연결 worker 생명주기/registry와 송수신 요청을 관리합니다. 구체 Transport/Worker
생성은 ConnectionSessionFactory, packet parser 세션은 PacketParserManager에 위임합니다.
"""
from typing import Dict, List, Optional

from PyQt5.QtCore import QObject, pyqtSignal

from common.dtos import PacketEvent, PortConfig, PortConnectionEvent, PortDataEvent, PortErrorEvent
from common.constants import REOPEN_FLUSH_WAIT_MS
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

        # 직전 세션이 아직 TX 큐를 비우는 중이면 끝날 때까지 잠깐 기다린다.
        # WHY: close는 비동기라 registry에서는 이미 사라졌지만 transport는 드레인이
        #      끝날 때까지 열려 있다. 그대로 열면 같은 물리 포트를 두 번 여는 시도가
        #      되거나 이전 세션의 남은 TX가 새 세션과 섞인다.
        #
        #      곧바로 거부하지 않는 이유는 "탭을 닫고 다시 열기"가 정당한 조작이기
        #      때문이다. 보통은 큐가 비어 있어 이 대기가 사실상 0이고, 실제 backlog가
        #      있을 때만 잠깐 기다린다. 상한을 넘기면 그때 알린다 — 여기서 무한정
        #      기다리면 close에서 없앤 멈춤이 open으로 옮겨갈 뿐이다.
        flushing = self._retired_workers.get(name)
        if flushing is not None and flushing.isRunning():
            if not flushing.wait(REOPEN_FLUSH_WAIT_MS):
                self._emit_error(
                    name,
                    "Previous session is still flushing queued data. "
                    "Please retry shortly.",
                )
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
        """세션 종료를 요청하고 **기다리지 않고** 반환합니다.

        WHY:
            큐에 남은 TX는 worker thread가 종료 직전에 끝까지 내보낸다 — 드레인에
            호출자의 thread는 필요하지 않다. 과거에는 `worker.stop()`이 무조건
            대기했기 때문에, 포트를 닫는 UI thread가 드레인이 끝날 때까지 멈췄다.
            저속 포트에 backlog가 쌓여 있으면 그만큼 창이 얼어붙는다.

            요청과 대기를 분리하면 **데이터는 그대로 다 내보내면서** UI는 기다리지
            않는다. 유실 없이 멈춤만 없앤 것이다.

        Note:
            registry 정리와 `connection_closed` 발행은 지금처럼 동기적으로 한다.
            그래야 호출 직후 `is_connection_open()`이 False가 되고 신규 송신이
            거부된다 — 드레인이 끝나기를 기다릴 필요가 없는 부분이다.

            프로세스가 곧 죽는 경로(앱 종료)에서는 이 메서드를 쓰면 안 된다.
            반드시 `close_all_and_wait()`로 드레인 완료를 기다려야 한다.
        """
        if name:
            worker = self.workers.get(name)
            if worker:
                self.connection_closing.emit(name)
                worker.request_stop()
                # worker의 cross-thread connection_closed는 main event loop에 queued될 수
                # 있으므로 registry는 요청 직후 동기적으로도 정리합니다.
                self.on_worker_closed(name, worker)
            return

        for port_name in list(self.workers.keys()):
            self.close_connection(port_name)

    def close_all_and_wait(self, timeout_ms: Optional[int] = None) -> bool:
        """모든 세션 종료를 요청하고 TX 드레인이 실제로 끝날 때까지 기다립니다.

        WHY:
            앱 종료처럼 프로세스가 곧 사라지는 경로에서는 비동기 close를 쓸 수 없다.
            기다리지 않으면 아직 내보내지 못한 TX 큐가 프로세스와 함께 사라진다 —
            기다리지 않는 것이 곧 유실이다.

        Args:
            timeout_ms: 세션당 대기 상한(ms). None이면 완료까지 무한 대기해
                유실을 만들지 않는다.

        Returns:
            bool: 모든 worker가 상한 안에 종료됐으면 True.
        """
        self.close_connection()
        return self.wait_for_pending_flush(timeout_ms=timeout_ms)

    def wait_for_pending_flush(self, timeout_ms: Optional[int] = None) -> bool:
        """이미 종료 요청된 worker들의 TX 드레인 완료를 기다립니다."""
        all_finished = True

        for name, worker in list(self._retired_workers.items()):
            if not worker.isRunning():
                continue

            if timeout_ms is None:
                worker.wait()
                continue

            if not worker.wait(timeout_ms):
                logger.warning(
                    f"Connection worker did not finish flushing within "
                    f"{timeout_ms} ms: {name}"
                )
                all_finished = False

        return all_finished

    def has_pending_flush(self) -> bool:
        """TX 드레인이 아직 끝나지 않은 세션이 있는지 반환합니다."""
        return any(worker.isRunning() for worker in self._retired_workers.values())

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
