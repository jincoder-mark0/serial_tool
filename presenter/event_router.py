"""
이벤트 라우터 모듈

EventBus와 Presenter/View 사이의 이벤트를 라우팅합니다.

## WHY
* EventBus의 범용 이벤트를 PyQt Signal로 변환하여 타입 안전성 확보
* UI Thread에서 안전한 이벤트 처리 보장 (Qt Signal/Slot 메커니즘 활용)
* Model 이벤트를 Presenter가 쉽게 구독할 수 있도록 중재

## WHAT
* EventBus 이벤트 구독 및 PyQt Signal 발행
* 포트 이벤트 라우팅 (Open, Close, Error, RX/TX Data, Packet)
* 매크로 이벤트 라우팅 (Start, Finish, Error)
* 파일 전송 이벤트 라우팅 (Progress, Complete, Error)

## HOW
* QObject 상속으로 PyQt Signal 제공
* EventBus.subscribe로 이벤트 구독
* 콜백에서 데이터를 추출하여 PyQt Signal emit
"""
from PyQt5.QtCore import QObject, pyqtSignal
from core.event_bus import event_bus
from common.dtos import PortDataEvent, PortErrorEvent, PacketEvent

class EventRouter(QObject):
    """
    EventBus ↔ PyQt Signal 변환기

    비동기 스레드에서 발생하는 EventBus 이벤트를
    메인 스레드(UI)에서 안전하게 처리할 수 있도록 PyQt 시그널로 변환합니다.
    """

    # ---------------------------------------------------------
    # 1. Port Events
    # ---------------------------------------------------------
    port_opened = pyqtSignal(str)
    port_closed = pyqtSignal(str)
    port_error = pyqtSignal(object)          # PortErrorEvent
    data_received = pyqtSignal(object)       # PortDataEvent
    data_sent = pyqtSignal(object)           # PortDataEvent
    packet_received = pyqtSignal(object)     # PacketEvent

    # ---------------------------------------------------------
    # 2. Macro Events
    # ---------------------------------------------------------
    macro_started = pyqtSignal()
    macro_finished = pyqtSignal()
    macro_error = pyqtSignal(str)              # error_message

    # ---------------------------------------------------------
    # 3. File Transfer Events
    # ---------------------------------------------------------
    file_transfer_progress = pyqtSignal(int, int)  # current_bytes, total_bytes
    file_transfer_completed = pyqtSignal(bool)     # success
    file_transfer_error = pyqtSignal(str)          # error_message

    def __init__(self):
        """EventRouter 초기화 및 이벤트 구독"""
        super().__init__()
        self.bus = event_bus
        self._subscribe_events()

    def _subscribe_events(self):
        """
        EventBus 이벤트 구독 설정

        Logic:
            - 각 도메인별(Port, Macro, File) 이벤트 토픽 구독
            - 핸들러 메서드 연결
        """
        # Port Events
        self.bus.subscribe("port.opened", self._on_port_opened)
        self.bus.subscribe("port.closed", self._on_port_closed)

        # DTO를 그대로 emit
        self.bus.subscribe("port.error", self._on_port_error)
        self.bus.subscribe("port.data_received", self._on_data_received)
        self.bus.subscribe("port.data_sent", self._on_data_sent)
        self.bus.subscribe("port.packet_received", self._on_packet_received)

        # Macro Events
        self.bus.subscribe("macro.started", lambda _: self.macro_started.emit())
        self.bus.subscribe("macro.finished", lambda _: self.macro_finished.emit())
        self.bus.subscribe("macro.error", self._on_macro_error)

        # File Transfer Events
        self.bus.subscribe("file.progress", self._on_file_progress)
        self.bus.subscribe("file.completed", self._on_file_completed)
        self.bus.subscribe("file.error", self._on_file_error)

    # ---------------------------------------------------------
    # Event Handlers (Port)
    # ---------------------------------------------------------
    def _on_port_opened(self, port_name: str):
        """포트 열림 이벤트 처리"""
        self.port_opened.emit(port_name)

    def _on_port_closed(self, port_name: str):
        """포트 닫힘 이벤트 처리"""
        self.port_closed.emit(port_name)

    def _on_port_error(self, event):
        """포트 에러 이벤트 처리"""
        if isinstance(event, PortErrorEvent):
            self.port_error.emit(event)
        elif isinstance(event, dict): # Legacy support
            self.port_error.emit(PortErrorEvent(event.get('port'), event.get('message')))

    def _on_data_received(self, event):
        """포트 데이터 수신 이벤트 처리"""
        if isinstance(event, PortDataEvent):
            self.data_received.emit(event)
        elif isinstance(event, dict):
            self.data_received.emit(PortDataEvent(event.get('port'), event.get('data')))

    def _on_data_sent(self, event):
        """포트 데이터 송신 이벤트 처리"""
        if isinstance(event, PortDataEvent):
            self.data_sent.emit(event)
        elif isinstance(event, dict):
            self.data_sent.emit(PortDataEvent(event.get('port'), event.get('data')))

    def _on_packet_received(self, event):
        """패킷 파싱 완료 이벤트 처리"""
        if isinstance(event, PacketEvent):
            self.packet_received.emit(event)
        elif isinstance(event, dict):
            self.packet_received.emit(PacketEvent(event.get('port'), event.get('packet')))

    # ---------------------------------------------------------
    # Event Handlers (Macro)
    # ---------------------------------------------------------
    def _on_macro_error(self, error_msg: str):
        """매크로 에러 이벤트 처리"""
        self.macro_error.emit(str(error_msg))

    # ---------------------------------------------------------
    # Event Handlers (File Transfer)
    # ---------------------------------------------------------
    def _on_file_progress(self, data: dict):
        """파일 전송 진행률 이벤트 처리"""
        self.file_transfer_progress.emit(data.get('current', 0), data.get('total', 0))

    def _on_file_completed(self, success: bool):
        """파일 전송 완료 이벤트 처리"""
        self.file_transfer_completed.emit(success)

    def _on_file_error(self, error_msg: str):
        """파일 전송 에러 이벤트 처리"""
        self.file_transfer_error.emit(str(error_msg))
