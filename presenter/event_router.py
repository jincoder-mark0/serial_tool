from PyQt5.QtCore import QObject, pyqtSignal
from typing import Any
from core.event_bus import event_bus

class EventRouter(QObject):
    """
    EventBus와 Presenter/View 사이의 이벤트를 라우팅하는 클래스입니다.
    EventBus의 이벤트를 구독하고, 이를 PyQt 시그널로 변환하여 UI 스레드에서 안전하게 처리할 수 있도록 합니다.
    """
    
    # Port Events
    port_opened = pyqtSignal(str)
    port_closed = pyqtSignal(str)
    port_error = pyqtSignal(str, str)
    data_received = pyqtSignal(str, bytes)
    
    # Macro Events
    macro_started = pyqtSignal()
    macro_finished = pyqtSignal()
    macro_progress = pyqtSignal(int, int) # current, total
    
    # File Transfer Events
    file_transfer_progress = pyqtSignal(int, int) # current, total
    file_transfer_completed = pyqtSignal(bool)
    
    def __init__(self):
        super().__init__()
        self.bus = event_bus
        self._subscribe_events()
        
    def _subscribe_events(self):
        """EventBus 이벤트 구독"""
        self.bus.subscribe("port.opened", self._on_port_opened)
        self.bus.subscribe("port.closed", self._on_port_closed)
        self.bus.subscribe("port.error", self._on_port_error)
        self.bus.subscribe("port.data_received", self._on_data_received)
        
        self.bus.subscribe("macro.started", lambda _: self.macro_started.emit())
        self.bus.subscribe("macro.finished", lambda _: self.macro_finished.emit())
        
        self.bus.subscribe("file.progress", self._on_file_progress)
        self.bus.subscribe("file.completed", self._on_file_completed)
        
    def _on_port_opened(self, port_name: str):
        self.port_opened.emit(port_name)
        
    def _on_port_closed(self, port_name: str):
        self.port_closed.emit(port_name)
        
    def _on_port_error(self, data: dict):
        self.port_error.emit(data.get('port', ''), data.get('message', ''))
        
    def _on_data_received(self, data: dict):
        self.data_received.emit(data.get('port', ''), data.get('data', b''))
        
    def _on_file_progress(self, data: dict):
        self.file_transfer_progress.emit(data.get('current', 0), data.get('total', 0))
        
    def _on_file_completed(self, success: bool):
        self.file_transfer_completed.emit(success)
