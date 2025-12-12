"""
이벤트 라우터 모듈

EventBus와 Presenter/View 사이의 이벤트를 라우팅합니다.

## WHY
* EventBus의 범용 이벤트를 PyQt Signal로 변환
* UI Thread에서 안전한 이벤트 처리 보장
* Model 이벤트를 Presenter가 쉽게 구독할 수 있도록 중재
* 타입 안전성 제공 (PyQt Signal의 타입 힌트 활용)

## WHAT
* EventBus 이벤트 구독 및 PyQt Signal 발행
* 포트 이벤트 라우팅 (opened, closed, error, data_received, data_sent)
* 매크로 이벤트 라우팅 (started, finished, progress)
* 파일 전송 이벤트 라우팅 (progress, completed)

## HOW
* QObject 상속으로 PyQt Signal 제공
* EventBus.subscribe로 이벤트 구독
* 콜백에서 PyQt Signal emit
* Dictionary 데이터를 개별 인자로 분해하여 전달
"""
from PyQt5.QtCore import QObject, pyqtSignal
from core.event_bus import event_bus

class EventRouter(QObject):
    """
    EventBus ↔ PyQt Signal 변환기

    EventBus의 범용 이벤트를 타입 안전한 PyQt Signal로 변환합니다.
    """

    # Port Events
    port_opened = pyqtSignal(str)
    port_closed = pyqtSignal(str)
    port_error = pyqtSignal(str, str)  # port_name, error_message
    data_received = pyqtSignal(str, bytes)  # port_name, data
    data_sent = pyqtSignal(str, bytes)  # [New] port_name, data

    # Macro Events
    macro_started = pyqtSignal()
    macro_finished = pyqtSignal()
    macro_progress = pyqtSignal(int, int)  # current, total

    # File Transfer Events
    file_transfer_progress = pyqtSignal(int, int)  # current, total
    file_transfer_completed = pyqtSignal(bool)  # success

    def __init__(self):
        """EventRouter 초기화 및 이벤트 구독"""
        super().__init__()
        self.bus = event_bus
        self._subscribe_events()

    def _subscribe_events(self):
        """
        EventBus 이벤트 구독

        Logic:
            - 포트 관련 이벤트 구독 및 핸들러 연결
            - 매크로 이벤트 구독 (Lambda로 간단 처리)
            - 파일 전송 이벤트 구독 및 핸들러 연결
        """
        # Port Events
        self.bus.subscribe("port.opened", self._on_port_opened)
        self.bus.subscribe("port.closed", self._on_port_closed)
        self.bus.subscribe("port.error", self._on_port_error)
        self.bus.subscribe("port.data_received", self._on_data_received)
        self.bus.subscribe("port.data_sent", self._on_data_sent)

        # Macro Events (간단한 이벤트는 Lambda 사용)
        self.bus.subscribe("macro.started", lambda _: self.macro_started.emit())
        self.bus.subscribe("macro.finished", lambda _: self.macro_finished.emit())

        # File Transfer Events
        self.bus.subscribe("file.progress", self._on_file_progress)
        self.bus.subscribe("file.completed", self._on_file_completed)

    def _on_port_opened(self, port_name: str):
        """포트 열림 이벤트 → PyQt Signal"""
        self.port_opened.emit(port_name)

    def _on_port_closed(self, port_name: str):
        """포트 닫힘 이벤트 → PyQt Signal"""
        self.port_closed.emit(port_name)

    def _on_port_error(self, data: dict):
        """포트 에러 이벤트 → PyQt Signal (Dictionary 분해)"""
        self.port_error.emit(data.get('port', ''), data.get('message', ''))

    def _on_data_received(self, data: dict):
        """데이터 수신 이벤트 → PyQt Signal (Dictionary 분해)"""
        self.data_received.emit(data.get('port', ''), data.get('data', b''))

    def _on_data_sent(self, data: dict):
        """데이터 송신 이벤트 → PyQt Signal (Dictionary 분해) [New]"""
        self.data_sent.emit(data.get('port', ''), data.get('data', b''))

    def _on_file_progress(self, data: dict):
        """파일 전송 진행률 이벤트 → PyQt Signal (Dictionary 분해)"""
        self.file_transfer_progress.emit(data.get('current', 0), data.get('total', 0))

    def _on_file_completed(self, success: bool):
        """파일 전송 완료 이벤트 → PyQt Signal"""
        self.file_transfer_completed.emit(success)
