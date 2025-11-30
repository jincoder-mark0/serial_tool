from PyQt5.QtCore import QObject, pyqtSignal
from typing import Any, Dict, List, Callable
import logging

class EventBus(QObject):
    """
    애플리케이션 전역 이벤트 버스입니다.
    Singleton 패턴으로 구현되어 어디서든 접근 가능합니다.
    PyQt의 Signal/Slot을 사용하여 스레드 간 안전한 통신을 지원합니다.
    """
    _instance = None
    
    # 모든 이벤트를 전달하는 제네릭 시그널 (topic, data)
    # data는 어떤 객체든 될 수 있습니다.
    _event_signal = pyqtSignal(str, object)

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EventBus, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        super().__init__()
        if not hasattr(self, '_initialized'):
            self._logger = logging.getLogger("EventBus")
            self._initialized = True

    def publish(self, topic: str, data: Any = None) -> None:
        """
        이벤트를 발행합니다.
        
        Args:
            topic: 이벤트 주제 (예: "port.opened", "rx.data")
            data: 전달할 데이터
        """
        # self._logger.debug(f"Publishing event: {topic}")
        self._event_signal.emit(topic, data)

    def subscribe(self, topic: str, callback: Callable[[Any], None]) -> None:
        """
        특정 토픽을 구독합니다.
        주의: 현재 구현에서는 모든 이벤트가 시그널을 통해 전달되므로,
        콜백 내부에서 토픽을 필터링하는 로직이 필요할 수 있습니다.
        
        더 나은 방식: 컴포넌트에서 event_bus.event_signal.connect(self.on_event) 후
        on_event에서 topic 확인.
        
        이 메서드는 편의를 위해 제공되지만, Qt의 스레드 오토 커넥션을 완벽히 활용하려면
        직접 시그널에 연결하는 것이 좋습니다.
        """
        # 단순 연결 (필터링 없음, 모든 이벤트를 받음)
        # 실제로는 EventRouter 등에서 필터링하여 처리하는 것을 권장.
        self._event_signal.connect(lambda t, d: callback(d) if t == topic else None)

    @property
    def signal(self) -> pyqtSignal:
        """이벤트 시그널에 직접 접근"""
        return self._event_signal
