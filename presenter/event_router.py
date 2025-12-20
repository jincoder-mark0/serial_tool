"""
이벤트 라우터 모듈

EventBus와 Presenter/View 사이의 이벤트를 라우팅합니다.

## WHY
* EventBus의 범용 이벤트를 PyQt Signal로 변환하여 타입 안전성 확보
* UI Thread에서 안전한 이벤트 처리 보장

## WHAT
* EventBus 이벤트 구독 및 PyQt Signal 발행
* 포트, 매크로, 파일, 시스템 이벤트 라우팅

## HOW
* QObject 상속으로 PyQt Signal 제공
* EventBus.subscribe로 이벤트 구독 후 Signal emit
"""
from PyQt5.QtCore import QObject, pyqtSignal
from core.event_bus import event_bus
from common.dtos import PortDataEvent, PortErrorEvent, PacketEvent, FileProgressEvent, PreferencesState
from common.constants import EventTopics

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
    port_error = pyqtSignal(object)
    data_received = pyqtSignal(object)
    data_sent = pyqtSignal(object)
    packet_received = pyqtSignal(object)

    # ---------------------------------------------------------
    # 2. Macro Events
    # ---------------------------------------------------------
    macro_started = pyqtSignal()
    macro_finished = pyqtSignal()
    macro_error = pyqtSignal(str)

    # ---------------------------------------------------------
    # 3. File Transfer Events
    # ---------------------------------------------------------
    file_transfer_progress = pyqtSignal(object)
    file_transfer_completed = pyqtSignal(bool)
    file_transfer_error = pyqtSignal(str)

    # ---------------------------------------------------------
    # 4. System Events
    # ---------------------------------------------------------
    settings_changed = pyqtSignal(object) # PreferencesState DTO

    def __init__(self):
        """EventRouter 초기화 및 이벤트 구독"""
        super().__init__()
        self.bus = event_bus
        self._subscribe_events()

    def _subscribe_events(self):
        """
        EventBus 이벤트 구독 설정

        Logic:
            - 각 도메인별(Port, Macro, File, System) 이벤트 토픽 구독
            - 핸들러 메서드 연결
        """
        # Port Events
        self.bus.subscribe(EventTopics.PORT_OPENED, self._on_port_opened)
        self.bus.subscribe(EventTopics.PORT_CLOSED, self._on_port_closed)

        # DTO를 그대로 emit
        self.bus.subscribe(EventTopics.PORT_ERROR, self._on_port_error)
        self.bus.subscribe(EventTopics.PORT_DATA_RECEIVED, self._on_data_received)
        self.bus.subscribe(EventTopics.PORT_DATA_SENT, self._on_data_sent)
        self.bus.subscribe(EventTopics.PORT_PACKET_RECEIVED, self._on_packet_received)

        # Macro Events
        self.bus.subscribe(EventTopics.MACRO_STARTED, lambda _: self.macro_started.emit())
        self.bus.subscribe(EventTopics.MACRO_FINISHED, lambda _: self.macro_finished.emit())
        self.bus.subscribe(EventTopics.MACRO_ERROR, self._on_macro_error)

        # File Transfer Events
        self.bus.subscribe(EventTopics.FILE_PROGRESS, self._on_file_progress)
        self.bus.subscribe(EventTopics.FILE_COMPLETED, self._on_file_completed)
        self.bus.subscribe(EventTopics.FILE_ERROR, self._on_file_error)

        # System Events
        self.bus.subscribe(EventTopics.SETTINGS_CHANGED, self._on_settings_changed)

    # ---------------------------------------------------------
    # Event Handlers (Port)
    # ---------------------------------------------------------
    def _on_port_opened(self, port_name: str):
        """포트 열림 이벤트 처리"""
        self.port_opened.emit(port_name)

    def _on_port_closed(self, port_name: str):
        """포트 닫힘 이벤트 처리"""
        self.port_closed.emit(port_name)

    def _on_port_error(self, event: PortErrorEvent):
        """포트 에러 이벤트 처리"""
        self.port_error.emit(event)

    def _on_data_received(self, event: PortDataEvent):
        """포트 데이터 수신 이벤트 처리"""
        self.data_received.emit(event)

    def _on_data_sent(self, event: PortDataEvent):
        """포트 데이터 송신 이벤트 처리"""
        self.data_sent.emit(event)

    def _on_packet_received(self, event: PacketEvent):
        """패킷 파싱 완료 이벤트 처리"""
        self.packet_received.emit(event)

    # ---------------------------------------------------------
    # Event Handlers (Macro)
    # ---------------------------------------------------------
    def _on_macro_error(self, error_msg: str):
        """매크로 에러 이벤트 처리"""
        self.macro_error.emit(str(error_msg))

    # ---------------------------------------------------------
    # Event Handlers (File Transfer)
    # ---------------------------------------------------------
    def _on_file_progress(self, event: FileProgressEvent):
        """
        파일 전송 진행률 이벤트 처리

        Args:
            event: FileProgressEvent DTO
        """
        self.file_transfer_progress.emit(event)

    def _on_file_completed(self, success: bool):
        """파일 전송 완료 이벤트 처리"""
        self.file_transfer_completed.emit(success)

    def _on_file_error(self, error_msg: str):
        """파일 전송 에러 이벤트 처리"""
        self.file_transfer_error.emit(str(error_msg))

    # ---------------------------------------------------------
    # Event Handlers (System)
    # ---------------------------------------------------------
    def _on_settings_changed(self, state: PreferencesState):
        """설정 변경 이벤트 처리"""
        self.settings_changed.emit(state)
