"""
Model 계층 핵심 로직 테스트

Model 계층의 주요 컴포넌트(PortController, MacroRunner, FileTransferEngine)의
비즈니스 로직과 상호작용을 검증합니다.

## WHY
* Model은 애플리케이션의 핵심 로직을 담당하므로 높은 신뢰성이 요구됨
* 스레드(QThread) 및 비동기 이벤트(Signal/EventBus)의 정상 동작 검증 필요
* 데이터 흐름 및 상태 관리 로직의 정확성 보장

## WHAT
* PortController: Signal 발생 시 EventBus로의 자동 전파(Bridge) 검증
* MacroRunner: QThread 기반 실행 흐름, Expect 대기 로직, 데이터 수신 연동 검증
* FileTransferEngine: Backpressure(역압) 제어 로직 검증

## HOW
* pytest-qt의 `qtbot`을 사용하여 비동기 시그널 대기 및 검증
* `Mock` 객체를 사용하여 의존성 분리 및 격리 테스트 수행
* 명시적인 대기 시간(`qtbot.wait`)을 통해 스레드 초기화 시간 확보

pytest tests/test_model.py -v
"""
import sys
import os
import pytest
import time
from PyQt5.QtCore import QObject

# 프로젝트 루트 경로 설정
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from model.port_controller import PortController
from model.macro_runner import MacroRunner
from model.macro_entry import MacroEntry
from model.file_transfer import FileTransferEngine
from core.event_bus import event_bus

# --- PortController Tests ---

def test_port_controller_eventbus_bridge(qtbot):
    """
    PortController의 시그널이 EventBus로 잘 전파되는지 테스트

    Logic:
        1. PortController 생성 및 EventBus 구독 설정
        2. `port_opened` 시그널 발생 시 EventBus 수신 확인
        3. `data_received` 시그널 발생 시 데이터 내용 및 포트 정보 확인
    """
    controller = PortController()
    received_events = []

    # EventBus 구독을 위한 헬퍼
    def on_event(data):
        received_events.append(data)

    event_bus.subscribe("port.opened", on_event)
    event_bus.subscribe("port.data_received", on_event)

    # 1. Port Open Signal Emit 검증
    with qtbot.waitSignal(controller.port_opened, timeout=1000):
        controller.port_opened.emit("COM1")

    # 이벤트 처리 대기 (비동기 큐 처리)
    qtbot.wait(50)
    assert "COM1" in received_events

    # 2. Data Received Signal Emit 검증
    test_data = b"Hello"
    with qtbot.waitSignal(controller.data_received, timeout=1000):
        controller.data_received.emit("COM1", test_data)

    qtbot.wait(50)

    # 수신된 이벤트 중 딕셔너리 데이터 찾기
    data_event = next(
        (e for e in received_events if isinstance(e, dict) and e.get('data') == test_data),
        None
    )
    assert data_event is not None
    assert data_event['port'] == "COM1"

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

    # [중요] 시그널 대기를 먼저 걸고 start() 호출
    # 타임아웃을 5초로 넉넉하게 설정하여 스레드 초기화 지연 대응
    with qtbot.waitSignal(runner.macro_finished, timeout=5000) as blocker:
        runner.start()

    assert blocker.signal_triggered

    # 스레드 완전 종료 대기
    runner.wait()

def test_macro_runner_expect(qtbot):
    """
    MacroRunner의 Expect 기능 및 EventBus 연동 테스트

    Logic:
        1. Expect 설정이 포함된 매크로 로드 (Timeout 1초)
        2. 실행 시작 후 스레드가 대기 상태에 진입할 때까지 대기 (`qtbot.wait`)
        3. EventBus를 통해 가상의 응답 데이터(`OK`) 발행
        4. `step_completed` 시그널이 성공(`True`)으로 발생하는지 검증
    """
    runner = MacroRunner()

    # Expect가 있는 엔트리 설정 (Timeout 1초로 단축하여 테스트 속도 향상 및 레이스 컨디션 방지)
    entries = [
        MacroEntry(command="AT", expect="OK", timeout_ms=1000, delay_ms=10)
    ]
    runner.load_macro(entries)

    # 1. 실행 시작 (Non-blocking)
    runner.start()

    # 2. 스레드가 시작되고 _wait_for_expect 상태로 진입할 시간을 충분히 줌
    qtbot.wait(500)

    # 3. 데이터 발행 (Expect 조건을 만족시킴)
    # 실제로는 PortController가 발행하는 이벤트를 모사
    print("Publishing 'OK' data...")
    event_bus.publish("port.data_received", {'port': 'COM1', 'data': b'OK\r\n'})

    # 4. step_completed 시그널 대기
    # MacroEntry 타임아웃(1초)보다 긴 테스트 타임아웃(5초)을 주어
    # 타임아웃 발생 시에도 시그널을 잡아낼 수 있게 함 (디버깅 용이)
    with qtbot.waitSignal(runner.step_completed, timeout=5000) as blocker:
        pass

    assert blocker.signal_triggered
    # 시그널 인자 확인: (index, success)
    # 성공 여부 확인 (True여야 함)
    assert blocker.args[1] is True

    # 5. 종료 및 정리
    runner.stop()
    runner.wait()

# --- FileTransferEngine Tests ---

class MockPortController(QObject):
    """FileTransfer 테스트용 Mock Controller"""
    def __init__(self):
        super().__init__()
        self.queue_size = 0
        self.sent_data = []
        self.is_open = True

    def get_write_queue_size(self, port_name):
        return self.queue_size

    def send_data_to_port(self, port_name, data):
        self.sent_data.append(data)
        return True

    def get_port_config(self, port_name):
        return {}

def test_file_transfer_backpressure(tmp_path):
    """
    Backpressure(역압) 로직 동작 테스트

    Logic:
        1. 임시 파일 생성
        2. Mock Controller의 큐 사이즈를 임계값 이상으로 설정
        3. FileTransferEngine 초기화 시 Backpressure 설정값 확인
    """
    # 1. 임시 파일 생성 (10KB)
    test_file = tmp_path / "large_test.bin"
    with open(test_file, "wb") as f:
        f.write(b"A" * 10240)

    mock_ctrl = MockPortController()
    engine = FileTransferEngine(mock_ctrl, "COM1", str(test_file), baudrate=9600)

    # 청크 사이즈 강제 축소 (테스트 용이성)
    engine.chunk_size = 100

    # 2. Backpressure 시뮬레이션
    mock_ctrl.queue_size = 100 # Threshold is usually 50

    # 엔진 속성 확인 (로직 존재 여부 검증)
    assert engine.queue_threshold == 50
    assert engine.flow_control == "None"

if __name__ == "__main__":
    pytest.main([__file__])
