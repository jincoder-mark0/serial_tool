"""
이벤트 버스 (Event Bus) 모듈

컴포넌트 간의 느슨한 결합(Decoupling)을 위해 Publish/Subscribe 패턴을 제공합니다.

## WHY
* 여러 컴포넌트가 동일한 이벤트를 구독하여 확장성 향상
* 스레드 간 안전한 통신 메커니즘 제공

## WHAT
* Topic 기반 Publish/Subscribe 패턴 구현
* 스레드 안전한 이벤트 발행 및 구독
* 동적 구독자 추가/제거 지원
* 전역 싱글톤 인스턴스 제공 (event_bus)

## HOW
* PyQt의 Signal/Slot 메커니즘으로 스레드 안전성 보장
* Dictionary 기반 토픽별 콜백 관리
* 내부 시그널(_dispatch_signal)로 메인 스레드에서 디스패칭
* 에러 발생 시에도 다른 구독자에게 영향 없도록 격리
"""

from PyQt5.QtCore import QObject, pyqtSignal
from typing import Any, Callable, Dict, List
import logging

class EventBus(QObject):
    """
    애플리케이션 전역 이벤트 버스 클래스

    Topic 기반으로 이벤트를 발행하고 구독하는 Publish/Subscribe 패턴을 구현합니다.
    """

    # 내부 신호 전송용 시그널 (스레드 간 통신 브리지 역할)
    # 직접 연결하지 않고 publish/subscribe 메서드를 사용해야 합니다.
    _dispatch_signal = pyqtSignal(str, object)

    def __init__(self):
        """EventBus를 초기화합니다"""
        super().__init__()
        self._logger = logging.getLogger("EventBus")

        # 토픽별 콜백 리스트 저장소: { "topic_name": [callback1, callback2, ...] }
        self._subscribers: Dict[str, List[Callable[[Any], None]]] = {}

        # 내부 시그널을 디스패처 메서드에 연결
        self._dispatch_signal.connect(self._dispatch_event)

    def publish(self, topic: str, data: Any = None) -> None:
        """
        이벤트를 발행합니다

        이 메서드는 스레드 안전하며, 내부적으로 시그널을 emit하여
        메인 스레드(EventBus가 생성된 스레드)에서 구독자들을 호출하도록 합니다.

        Args:
            topic (str): 이벤트 주제 (예: "port.opened")
            data (Any, optional): 전달할 데이터. 기본값은 None
        """
        # 시그널을 통해 데이터 전달 -> _dispatch_event 슬롯 호출
        self._dispatch_signal.emit(topic, data)

    def subscribe(self, topic: str, callback: Callable[[Any], None]) -> None:
        """
        특정 토픽을 구독합니다

        Args:
            topic (str): 구독할 이벤트 주제
            callback (Callable[[Any], None]): 이벤트 발생 시 호출될 콜백 함수
        """
        if topic not in self._subscribers:
            self._subscribers[topic] = []

        if callback not in self._subscribers[topic]:
            self._subscribers[topic].append(callback)

    def unsubscribe(self, topic: str, callback: Callable[[Any], None]) -> None:
        """
        구독을 취소합니다

        Args:
            topic (str): 이벤트 주제
            callback (Callable): 제거할 콜백 함수
        """
        if topic in self._subscribers:
            try:
                self._subscribers[topic].remove(callback)
                if not self._subscribers[topic]:  # 리스트가 비면 키 삭제
                    del self._subscribers[topic]
            except ValueError:
                self._logger.warning(f"Callback not found for topic '{topic}' during unsubscribe.")

    def _dispatch_event(self, topic: str, data: Any) -> None:
        """
        내부적으로 이벤트를 실제 구독자들에게 전달하는 슬롯입니다

        이 메서드는 EventBus가 생성된 스레드(주로 Main Thread)에서 실행됩니다.

        Args:
            topic (str): 이벤트 주제
            data (Any): 전달된 데이터

        Logic:
            - 해당 토픽의 모든 구독자에게 데이터 전달
            - 각 콜백 실행 중 에러 발생 시 로깅하고 다음 콜백 계속 실행
            - 한 구독자의 에러가 다른 구독자에게 영향 없도록 격리
        """
        if topic in self._subscribers:
            for callback in self._subscribers[topic]:
                try:
                    callback(data)
                except Exception as e:
                    self._logger.error(f"Error processing event '{topic}': {e}", exc_info=True)

# 전역 EventBus 인스턴스
event_bus = EventBus()