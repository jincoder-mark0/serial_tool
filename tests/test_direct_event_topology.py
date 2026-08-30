"""
EventRouter/EventBus 제거 후 애플리케이션 이벤트 토폴로지 회귀 테스트.

## WHY
같은 사건을 Qt Signal -> 전역 Pub/Sub -> Router -> Qt Signal로 다시 중계하면
배선 경로가 이중화되고 구독 생명주기까지 별도로 관리해야 합니다. 현재 구조는
Model/Presenter의 DTO 기반 Qt Signal을 직접 연결하는 단일 경로를 사용합니다.
"""
import inspect
from pathlib import Path

import common.constants as constants
from model.connection_controller import ConnectionController
from model.file_transfer_service import FileTransferService
from model.macro_runner import MacroRunner
from presenter.main_presenter import MainPresenter
from presenter.packet_presenter import PacketPresenter


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_runtime_event_producers_do_not_depend_on_event_bus():
    for cls in (ConnectionController, MacroRunner, FileTransferService):
        source = inspect.getsource(cls)
        assert "event_bus" not in source
        assert "EventTopics" not in source


def test_main_presenter_does_not_use_event_router_or_event_bus():
    source = inspect.getsource(MainPresenter)
    assert "EventRouter" not in source
    assert "event_router" not in source
    assert "event_bus" not in source
    assert "EventTopics" not in source


def test_packet_presenter_consumes_connection_controller_directly():
    source = inspect.getsource(PacketPresenter)
    assert "ConnectionController" in source
    assert "EventRouter" not in source
    assert "event_router" not in source
    assert "connection_controller.packet_received.connect" in source
    assert "connection_controller.connection_closed.connect" in source


def test_macro_expect_input_is_public_direct_signal_slot():
    source = inspect.getsource(MacroRunner)
    assert "def on_data_received" in source
    assert "macro_started = pyqtSignal()" in source


def test_removed_event_relay_modules_and_topics_are_not_present():
    assert not (PROJECT_ROOT / "presenter" / "event_router.py").exists()
    assert not (PROJECT_ROOT / "core" / "event_bus.py").exists()
    assert "class EventTopics" not in inspect.getsource(constants)
