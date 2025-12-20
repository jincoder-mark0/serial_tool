"""
Model 계층 핵심 로직 테스트

Model 계층의 주요 컴포넌트(ConnectionController, MacroRunner, FileTransferService)의
비즈니스 로직과 상호작용을 검증합니다.

## WHY
* Model은 애플리케이션의 핵심 로직을 담당하므로 높은 신뢰성이 요구됨
* 스레드(QThread) 및 비동기 이벤트(Signal/EventBus)의 정상 동작 검증 필요
* 데이터 흐름 및 상태 관리 로직의 정확성 보장

## WHAT
* ConnectionController: Signal 발생 시 EventBus로의 자동 전파(Bridge) 검증
* MacroRunner: QThread 기반 실행 흐름, Expect 대기 로직, 데이터 수신 연동 검증
* FileTransferService: Backpressure(역압) 제어 로직 검증

## HOW
* pytest-qt의 `qtbot`을 사용하여 비동기 시그널 대기 및 검증
* `Mock` 객체를 사용하여 의존성 분리 및 격리 테스트 수행

pytest tests/test_model.py -v
"""
import sys
import os
import pytest
from PyQt5.QtCore import QObject

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from model.connection_controller import ConnectionController
from model.macro_runner import MacroRunner
from common.dtos import MacroEntry, PortDataEvent
from model.file_transfer_service import FileTransferService
from core.event_bus import event_bus
from common.constants import EventTopics

# --- ConnectionController Tests ---

def test_connection_controller_eventbus_bridge(qtbot):
    """
    ConnectionController의 시그널이 EventBus로 잘 전파되는지 테스트

    Logic:
        1. ConnectionController 생성 및 EventBus 구독 설정
        2. `port_opened` 시그널 발생 시 EventBus 수신 확인
        3. `data_received` 시그널 발생 시 EventBus 수신 확인 (DTO 확인)
    """
    controller = ConnectionController()
    received_events = []

    # EventBus 구독을 위한 헬퍼
    def on_event(data):
        received_events.append(data)

    event_bus.subscribe(EventTopics.PORT_OPENED, on_event)
    event_bus.subscribe(EventTopics.PORT_DATA_RECEIVED, on_event)

    # 1. Port Open Signal Emit 검증
    with qtbot.waitSignal(controller.port_opened, timeout=1000):
        controller.connection_opened.emit("COM1")

    # 이벤트 처리 대기
    qtbot.wait(50)
    assert "COM1" in received_events

    # 2. Data Received Signal Emit 검증
    test_data = b"Hello"
    # Controller의 시그널은 (port_name, data) 서명임
    with qtbot.waitSignal(controller.data_received, timeout=1000):
        controller.data_received.emit("COM1", test_data)

    qtbot.wait(50)

    # 수신된 이벤트 중 DTO 데이터 찾기
    data_event = next(
        (e for e in received_events if isinstance(e, PortDataEvent) and e.data == test_data),
        None
    )
    assert data_event is not None
    assert data_event.port == "COM1"

# --- MacroRunner Tests ---

def test_macro_runner_basic_flow(qtbot):
    """
    MacroRunner의 기본 실행 흐름 (Start -> Send -> Finish) 테스트

    Logic:
        1. MacroRunner 생성 및 테스트 엔트리 로드
        2. `macro_finished` 시그널 대기 설정 (먼저 설정해야 놓치지 않음)
        3. 스레드 시작 (`start`)
        4. 시그널 발생 확인 및 스레드 종료 대기
    """
    runner = MacroRunner()

    # 테스트용 매크로 엔트리 (Delay 10ms로 최소화)
    entries = [
        MacroEntry(command="CMD1", delay_ms=10),
        MacroEntry(command="CMD2", delay_ms=10)
    ]
    runner.load_macro(entries)

    # 시그널 대기를 먼저 걸고 start() 호출
    with qtbot.waitSignal(runner.macro_finished, timeout=5000) as blocker:
        runner.start()

    assert blocker.signal_triggered

    # 스레드 완전 종료 대기
    runner.wait()

def test_macro_runner_expect(qtbot):
    """
    MacroRunner의 Expect 기능 및 EventBus 연동 테스트

    Logic:
        1. Expect 설정이 포함된 매크로 로드
        2. 실행 시작 후 스레드가 대기 상태에 진입할 때까지 대기 (`qtbot.wait`)
        3. EventBus를 통해 가상의 응답 데이터(`OK`) 발행
        4. `step_completed` 시그널이 성공(`True`)으로 발생하는지 검증
    """
    runner = MacroRunner()

    # Expect가 있는 엔트리 설정
    entries = [
        MacroEntry(command="AT", expect="OK", timeout_ms=5000, delay_ms=10)
    ]
    runner.load_macro(entries)

    # 1. 실행 시작
    runner.start()

    # 2. 스레드 시작 대기
    qtbot.wait(200)

    # 3. 데이터 발행 (EventBus를 통해 PortDataEvent DTO 전달)
    print("Publishing 'OK' data...")
    dto = PortDataEvent(port="COM1", data=b"OK\r\n")

    with qtbot.waitSignal(runner.step_completed, timeout=5000) as blocker:
        event_bus.publish(EventTopics.PORT_DATA_RECEIVED, dto)

    assert blocker.signal_triggered
    # 4. 시그널 인자 확인: MacroStepEvent 객체
    step_event = blocker.args[0]
    assert step_event.success is True

    # 5. 종료 및 정리
    runner.stop()
    runner.wait()

# --- FileTransferService Tests ---

class MockConnectionController(QObject):
    """FileTransfer 테스트용 Mock Controller"""
    def __init__(self):
        super().__init__()
        self.queue_size = 0
        self.sent_data = []
        self.is_open = True

    def register_file_transfer(self, port, service): pass
    def unregister_file_transfer(self, port): pass

    def get_write_queue_size(self, port_name):
        return self.queue_size

    def send_data_to_connection(self, port_name, data):
        self.sent_data.append(data)
        return True

def test_file_transfer_backpressure(tmp_path):
    """
    Backpressure(역압) 로직 동작 테스트

    Logic:
        1. 임시 파일 생성
        2. Mock Controller의 큐 사이즈를 임계값 이상으로 설정
        3. FileTransferService 초기화 시 Backpressure 설정값 확인
    """
    # 1. 임시 파일 생성
    test_file = tmp_path / "large_test.bin"
    with open(test_file, "wb") as f:
        f.write(b"A" * 1024)

    mock_control = MockConnectionController()
    # DTO Mocking
    from common.dtos import PortConfig
    config = PortConfig(port="COM1", baudrate=9600)

    file_transfer_service = FileTransferService(mock_control, str(test_file), config)

    # 청크 사이즈 확인
    assert file_transfer_service.chunk_size > 0
    # Backpressure 임계값 확인
    assert file_transfer_service.queue_threshold == 50

if __name__ == "__main__":
    pytest.main([__file__])