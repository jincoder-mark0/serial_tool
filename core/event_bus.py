from PyQt5.QtCore import QObject, pyqtSignal
from typing import Any, Callable
import logging

class EventBus(QObject):
    """
    애플리케이션 전역 이벤트 버스 클래스입니다.
    Singleton 패턴으로 구현되어 애플리케이션 어디서든 접근 가능합니다.
    PyQt의 Signal/Slot 메커니즘을 사용하여 스레드 간 안전한 통신을 지원합니다.
    """
    _instance = None
    
    # 모든 이벤트를 전달하는 제네릭 시그널 (topic, data)
    # data는 어떤 객체든 될 수 있습니다 (Any).
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
            topic (str): 이벤트 주제 (예: "port.opened", "rx.data").
            data (Any, optional): 전달할 데이터. 기본값은 None.
        """
        # self._logger.debug(f"Publishing event: {topic}")
        self._event_signal.emit(topic, data)

    def subscribe(self, topic: str, callback: Callable[[Any], None]) -> None:
        """
        특정 토픽을 구독합니다.
        
        주의: 현재 구현에서는 모든 이벤트가 단일 시그널을 통해 전달되므로,
        이 메서드는 내부적으로 람다를 사용하여 토픽을 필터링합니다.
        
        권장 사항: 컴포넌트에서 `event_bus.signal.connect(self.on_event)`를 사용하여
        직접 연결하고, `on_event` 메서드 내에서 토픽을 확인하는 것이
        Qt의 스레드 자동 연결(Auto Connection) 기능을 더 잘 활용하는 방법일 수 있습니다.
        
        Args:
            topic (str): 구독할 이벤트 주제.
            callback (Callable[[Any], None]): 이벤트 발생 시 호출될 콜백 함수.
        """
        # 단순 연결 (필터링 람다 사용)
        self._event_signal.connect(lambda t, d: callback(d) if t == topic else None)

    @property
    def signal(self) -> pyqtSignal:
        """
        이벤트 시그널 객체에 직접 접근합니다.
        
        Returns:
            pyqtSignal: (topic, data)를 전달하는 시그널.
        """
        return self._event_signal
