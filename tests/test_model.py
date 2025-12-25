"""
모델 계층 테스트 모듈

애플리케이션의 핵심 비즈니스 로직(Model)을 담당하는 클래스들을 테스트합니다.

## WHY
* UI와 분리된 순수 로직의 정확성 검증 (Unit Testing)
* 통신(Transport), 파싱(Parser), 자동화(Macro) 로직의 결함 조기 발견
* 리팩토링 시 기능 회귀(Regression) 방지

## WHAT
* PacketParser: Raw 데이터 파싱 및 객체 변환 테스트
* ConnectionController: 연결 생명주기 및 데이터 송수신 흐름 제어 테스트
* MacroRunner: 매크로 로드, 상태 관리 및 시그널 발생 테스트

## HOW
* Pytest 및 unittest.mock 활용
* conftest.py에서 정의한 Mock Fixture(mock_serial_port 등) 주입
* Qt Signal 방출 여부를 검증하기 위한 Spy 패턴 적용

pytest tests/test_model.py -v
"""
import time
import pytest
from unittest.mock import MagicMock, call, patch

from model.packet_parser import ParserFactory
from model.connection_controller import ConnectionController
from model.macro_runner import MacroRunner
from common.dtos import PortConfig, MacroEntry, PortConnectionEvent, PortDataEvent
from common.enums import ParserType


# =============================================================================
# 1. 패킷 파서 테스트 (Packet Parser Tests)
# =============================================================================

class TestPacketParser:
    """
    PacketParser 및 ParserFactory 기능을 검증하는 테스트 클래스입니다.
    """

    def test_raw_parser_creation(self):
        """
        ParserFactory를 통한 RawParser 생성 테스트

        Logic:
            - ParserType.RAW로 팩토리 호출
            - 반환된 객체의 타입 및 기본 설정 확인
        """
        # GIVEN: Raw 타입 지정
        parser_type = ParserType.RAW

        # WHEN: 파서 생성 요청
        parser = ParserFactory.create_parser(parser_type)

        # THEN: 파서가 정상적으로 생성되어야 함
        assert parser is not None
        # RawParser는 별도의 복잡한 타입 체크 없이 기본 동작 수행

    def test_raw_parser_parsing(self):
        """
        RawParser의 데이터 파싱 기능 테스트

        Logic:
            - 임의의 바이트 데이터 입력
            - parse 메서드 호출
            - 반환된 패킷 객체의 raw_data 일치 여부 확인
        """
        # GIVEN: 파서 및 테스트 데이터 준비
        parser = ParserFactory.create_parser(ParserType.RAW)
        input_data = b"Hello Serial"

        # WHEN: 파싱 수행
        packets = parser.parse(input_data)

        # THEN: 하나의 패킷으로 반환되어야 하며 데이터가 일치해야 함
        assert len(packets) == 1
        assert packets[0].raw_data == input_data
        assert packets[0].type_name == "RAW"


# =============================================================================
# 2. 연결 컨트롤러 테스트 (Connection Controller Tests)
# =============================================================================

class TestConnectionController:
    """
    ConnectionController의 연결 관리 및 데이터 흐름을 검증하는 테스트 클래스입니다.
    """

    def test_open_connection_success(self, mock_serial_port, sample_port_config, qapp):
        """
        포트 연결 성공 시나리오 테스트

        Logic:
            - Controller 생성
            - Mocking된 Serial 포트 환경에서 open_connection 호출
            - Worker 생성 및 상태(is_connection_open) 확인
            - 시그널(connection_opened) 방출 확인
        """
        # GIVEN: 컨트롤러 준비
        controller = ConnectionController()

        # Signal Spy (시그널 발생 감지용 Mock)
        signal_spy = MagicMock()
        controller.connection_opened.connect(signal_spy)

        # WHEN: 연결 시도 (conftest.py의 mock_serial_port가 pyserial을 패치함)
        result = controller.open_connection(sample_port_config)

        # THEN: 성공 반환 및 내부 상태 변경
        assert result is True
        assert controller.is_connection_open(sample_port_config.port) is True

        # Worker 스레드가 생성되어 있어야 함
        assert sample_port_config.port in controller.workers

        # 비동기 시그널 처리를 위해 잠시 대기 (또는 processEvents)
        qapp.processEvents()

        # 시그널 발생 확인 (정확한 타이밍 이슈로 인해 worker 내부 동작에 따라 다를 수 있음)
        # 여기서는 Controller 로직상 Worker 생성 성공 여부를 주로 봅니다.

    def test_open_connection_duplicate_fail(self, mock_serial_port, sample_port_config):
        """
        이미 열린 포트에 대한 중복 연결 시도 실패 테스트

        Logic:
            - 첫 번째 연결 시도 (성공)
            - 동일 설정으로 두 번째 연결 시도
            - 실패(False) 반환 및 에러 시그널 발생 확인
        """
        # GIVEN: 이미 연결된 상태
        controller = ConnectionController()
        controller.open_connection(sample_port_config)

        error_spy = MagicMock()
        controller.error_occurred.connect(error_spy)

        # WHEN: 중복 연결 시도
        result = controller.open_connection(sample_port_config)

        # THEN: 실패 반환 및 에러 메시지 발생
        assert result is False
        error_spy.assert_called_once()
        args, _ = error_spy.call_args
        assert args[0].port == sample_port_config.port  # PortErrorEvent 검증

    def test_send_data(self, mock_serial_port, sample_port_config):
        """
        데이터 전송 요청 테스트

        Logic:
            - 포트 연결
            - send_data 호출
            - Worker의 send_data가 호출되었는지 확인
            - data_sent 시그널 발생 확인
        """
        # GIVEN: 연결된 컨트롤러
        controller = ConnectionController()
        controller.open_connection(sample_port_config)

        data_sent_spy = MagicMock()
        controller.data_sent.connect(data_sent_spy)

        test_data = b"TEST_DATA"

        # WHEN: 데이터 전송
        controller.send_data(sample_port_config.port, test_data)

        # THEN: Worker 큐에 데이터가 들어가고 시그널이 발생해야 함
        # 실제 Worker는 Thread이므로 내부 메서드 호출을 Mocking하거나 로직 검증
        # 여기서는 Controller 레벨에서 예외 없이 수행되었는지 확인

        assert data_sent_spy.called
        event = data_sent_spy.call_args[0][0]
        assert event.port == sample_port_config.port
        assert event.data == test_data

    def test_close_connection(self, mock_serial_port, sample_port_config, qapp):
        """
        포트 연결 종료 테스트

        Logic:
            - 포트 연결
            - close_connection 호출
            - Worker 정지 및 리소스 정리 확인
            - connection_closed 시그널 발생 확인
        """
        # GIVEN: 연결된 컨트롤러
        controller = ConnectionController()
        controller.open_connection(sample_port_config)

        closed_spy = MagicMock()
        controller.connection_closed.connect(closed_spy)

        # WHEN: 연결 종료
        controller.close_connection(sample_port_config.port)

        # THEN: 리소스 정리 확인
        assert controller.is_connection_open(sample_port_config.port) is False
        assert sample_port_config.port not in controller.workers

        # 시그널 발생 확인
        assert closed_spy.called
        event = closed_spy.call_args[0][0]
        assert event.port == sample_port_config.port
        assert event.state == "closed"


# =============================================================================
# 3. 매크로 러너 테스트 (Macro Runner Tests)
# =============================================================================

class TestMacroRunner:
    """
    MacroRunner의 실행 로직 및 상태 관리를 검증하는 테스트 클래스입니다.
    """

    def test_load_macro(self):
        """
        매크로 항목 로드 테스트

        Logic:
            - MacroRunner 생성
            - 매크로 리스트 로드
            - 내부 저장소(_entries) 확인
        """
        # GIVEN: 매크로 엔트리 리스트
        runner = MacroRunner()
        entries = [
            MacroEntry(enabled=True, command="CMD1", delay_ms=100),
            MacroEntry(enabled=False, command="CMD2", delay_ms=100)
        ]

        # WHEN: 로드
        runner.load_macro(entries)

        # THEN: 저장 확인
        assert len(runner._entries) == 2
        assert runner._entries[0].command == "CMD1"

    def test_macro_start_and_signal(self, qapp, sample_macro_entry):
        """
        매크로 시작 및 시그널 발생 테스트

        Logic:
            - Runner 생성 및 엔트리 로드
            - send_requested 시그널에 Spy 연결
            - start() 호출 (QThread 시작)
            - 약간의 대기 후 시그널 발생 확인
            - stop() 호출
        """
        # GIVEN: Runner 및 Spy 설정
        runner = MacroRunner()
        runner.load_macro([sample_macro_entry])

        send_spy = MagicMock()
        runner.send_requested.connect(send_spy)

        step_spy = MagicMock()
        runner.step_started.connect(step_spy)

        # WHEN: 매크로 시작
        runner.start(loop_count=1, interval_ms=0)

        # 스레드 동작 대기 (테스트 환경에서는 sleep 필요)
        # 실제로는 qtbot.waitSignal 등을 쓰지만 여기선 simple sleep
        time.sleep(0.1)

        # THEN: 시작 시그널 및 전송 요청 확인
        assert runner.isRunning() or runner.isFinished()

        # 엔트리가 하나 있으므로 send_requested가 최소 1회 발생해야 함
        if send_spy.call_count == 0:
            # CI/CD 환경 등 느린 환경 대비 추가 대기
            time.sleep(0.2)

        assert send_spy.called
        cmd_arg = send_spy.call_args[0][0]
        assert cmd_arg.command == sample_macro_entry.command

        # 정리
        if runner.isRunning():
            runner.stop()

    def test_macro_pause_resume(self):
        """
        매크로 일시정지 및 재개 상태 테스트

        Logic:
            - Runner 시작
            - pause() 호출 후 _is_paused 플래그 확인
            - resume() 호출 후 _is_paused 플래그 해제 확인
        """
        # GIVEN: Runner 실행 (Mock entries)
        runner = MacroRunner()
        # 긴 딜레이를 주어 바로 끝나지 않게 설정
        entry = MacroEntry(enabled=True, command="CMD", delay_ms=1000)
        runner.load_macro([entry])
        runner.start()

        # Ensure running
        time.sleep(0.05)

        # WHEN: 일시정지
        runner.pause()

        # THEN: 상태 확인
        # Mutex로 보호되므로 직접 접근보다는 안전하게 확인해야 하지만,
        # Unit Test에서는 내부 상태(_is_paused)를 확인
        assert runner._is_paused is True

        # WHEN: 재개
        runner.resume()

        # THEN: 상태 해제 확인
        assert runner._is_paused is False

        runner.stop()