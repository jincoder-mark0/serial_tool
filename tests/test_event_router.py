"""
S-045 커버리지 테스트: EventRouter (presenter/event_router.py)

## WHY
* `EventRouter._subscribe_events()`는 EventBus 토픽 문자열과 핸들러를 1:1로
  연결하는 배선(wiring) 코드다. 토픽 오타나 구독 누락은 파이썬 문법 오류를
  일으키지 않고 그냥 "그 이벤트만 조용히 아무 반응이 없는" 형태로 나타나서
  실제로 이벤트를 publish해 보지 않으면 잡히지 않는다. 이 파일은 기존에
  테스트가 0건이었다.

## WHAT
* `EventRouter()`를 생성해 실제 `_subscribe_events()`가 실행되게 한 뒤,
  EventBus의 각 토픽(`common/constants.py`의 EventTopics)에 실제로 publish하여
  대응하는 PyQt 시그널이 올바른 DTO와 함께 발생하는지 전부 확인한다.

## HOW
* `event_bus.publish(topic, data)`는 같은 스레드에서 Direct Connection으로
  동기 처리되므로, 시그널을 리스트에 append하는 슬롯을 연결해두면 publish 직후
  바로 확인할 수 있다(스레드 대기 불필요).
* `tests/conftest.py`의 `reset_event_bus` autouse fixture가 각 테스트 전후로
  EventBus 구독자 목록을 초기화하므로 테스트 간 간섭이 없다.
"""
import pytest

from core.event_bus import event_bus
from common.constants import EventTopics
from common.dtos import (
    PortConnectionEvent,
    PortErrorEvent,
    PortDataEvent,
    PacketEvent,
    MacroErrorEvent,
    FileProgressEvent,
    FileCompletionEvent,
    FileErrorEvent,
    PreferencesState,
)
from presenter.event_router import EventRouter


@pytest.fixture
def router(qapp):
    """실제 _subscribe_events()가 수행된 EventRouter 인스턴스."""
    return EventRouter()


# -----------------------------------------------------------------------------
# Port Events
# -----------------------------------------------------------------------------

def test_port_opened_topic_routes_to_signal(router):
    received = []
    router.port_opened.connect(received.append)

    event = PortConnectionEvent(port="COM1", state="opened")
    event_bus.publish(EventTopics.PORT_OPENED, event)

    assert received == [event]


def test_port_closed_topic_routes_to_signal(router):
    received = []
    router.port_closed.connect(received.append)

    event = PortConnectionEvent(port="COM1", state="closed")
    event_bus.publish(EventTopics.PORT_CLOSED, event)

    assert received == [event]


def test_port_error_topic_routes_to_signal(router):
    received = []
    router.port_error.connect(received.append)

    event = PortErrorEvent(port="COM1", message="boom")
    event_bus.publish(EventTopics.PORT_ERROR, event)

    assert received == [event]


def test_port_data_received_topic_routes_to_signal(router):
    received = []
    router.data_received.connect(received.append)

    event = PortDataEvent(port="COM1", data=b"\x01\x02")
    event_bus.publish(EventTopics.PORT_DATA_RECEIVED, event)

    assert received == [event]


def test_port_data_sent_topic_routes_to_signal(router):
    received = []
    router.data_sent.connect(received.append)

    event = PortDataEvent(port="COM1", data=b"\x03\x04")
    event_bus.publish(EventTopics.PORT_DATA_SENT, event)

    assert received == [event]


def test_port_packet_received_topic_routes_to_signal(router):
    received = []
    router.packet_received.connect(received.append)

    event = PacketEvent(port="COM1", packet=object())
    event_bus.publish(EventTopics.PORT_PACKET_RECEIVED, event)

    assert received == [event]


# -----------------------------------------------------------------------------
# Macro Events
# -----------------------------------------------------------------------------

def test_macro_started_topic_routes_to_signal(router):
    calls = []
    router.macro_started.connect(lambda: calls.append(True))

    event_bus.publish(EventTopics.MACRO_STARTED, None)

    assert calls == [True]


def test_macro_finished_topic_routes_to_signal(router):
    calls = []
    router.macro_finished.connect(lambda: calls.append(True))

    event_bus.publish(EventTopics.MACRO_FINISHED, None)

    assert calls == [True]


def test_macro_error_topic_routes_to_signal(router):
    received = []
    router.macro_error.connect(received.append)

    event = MacroErrorEvent(message="macro failed", row_index=2)
    event_bus.publish(EventTopics.MACRO_ERROR, event)

    assert received == [event]


# -----------------------------------------------------------------------------
# File Transfer Events
# -----------------------------------------------------------------------------

def test_file_progress_topic_routes_to_signal(router):
    received = []
    router.file_transfer_progress.connect(received.append)

    event = FileProgressEvent(current=10, total=100)
    event_bus.publish(EventTopics.FILE_PROGRESS, event)

    assert received == [event]


def test_file_completed_topic_routes_to_signal(router):
    received = []
    router.file_transfer_completed.connect(received.append)

    event = FileCompletionEvent(success=True, message="done", file_path="a.bin")
    event_bus.publish(EventTopics.FILE_COMPLETED, event)

    assert received == [event]


def test_file_error_topic_routes_to_signal(router):
    received = []
    router.file_transfer_error.connect(received.append)

    event = FileErrorEvent(message="disk full", file_path="a.bin")
    event_bus.publish(EventTopics.FILE_ERROR, event)

    assert received == [event]


# -----------------------------------------------------------------------------
# System Events
# -----------------------------------------------------------------------------

def test_settings_changed_topic_routes_to_signal(router):
    received = []
    router.settings_changed.connect(received.append)

    state = PreferencesState(theme="Light", language="ko")
    event_bus.publish(EventTopics.SETTINGS_CHANGED, state)

    assert received == [state]


# -----------------------------------------------------------------------------
# 배선 누락/오타 회귀 방지 — 모든 토픽이 최소 1개 구독자를 갖는지 총점검
# -----------------------------------------------------------------------------

def test_all_event_topics_have_at_least_one_subscriber_after_router_init(router):
    """
    EventRouter 생성만으로 EventTopics에 정의된 모든 토픽이 최소 하나의
    구독자를 갖는지 확인한다. 토픽을 새로 추가하고 구독을 깜빡한 회귀를 잡는다.
    """
    all_topics = [
        value for name, value in vars(EventTopics).items()
        if not name.startswith("_") and isinstance(value, str)
    ]
    assert all_topics, "EventTopics에 문자열 상수가 하나도 없습니다 (테스트 전제 붕괴)"

    for topic in all_topics:
        assert topic in event_bus._subscribers, (
            f"토픽 '{topic}'을 구독하는 핸들러가 없습니다 (EventRouter._subscribe_events 누락 의심)"
        )
        assert len(event_bus._subscribers[topic]) >= 1
