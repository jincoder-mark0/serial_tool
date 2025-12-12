"""
매크로 실행 엔진 모듈

이 모듈은 사용자가 정의한 명령어 시퀀스를 자동으로 실행하는 매크로 엔진을 제공합니다.

## WHY
* 반복적인 명령어 입력 작업을 자동화하여 사용자 편의성 향상
* 복잡한 테스트 시나리오를 스크립트로 저장하고 재실행 가능
* 일정한 간격으로 명령어를 반복 전송하여 디바이스 테스트 자동화
* Main Thread(UI)와 분리된 정밀한 타이밍 제어 필요

## WHAT
* 매크로 항목(MacroEntry) 리스트를 순차적으로 실행
* QThread 기반의 독립 실행 환경 제공
* 정밀한 Delay 처리 및 즉각적인 Pause/Stop 지원
* Expect 기능을 위한 응답 대기 구조 포함 (EventBus 연동)
* 실행 상태(성공/실패)를 시그널로 외부에 전달

## HOW
* QThread 상속으로 UI 블로킹 없는 실행 보장
* QWaitCondition을 사용하여 타이밍 정밀도 확보 및 인터럽트 지원
* Mutex를 사용한 스레드 안전성 확보
* 상태 머신 패턴으로 실행 흐름 관리
* EventBus를 통해 수신 데이터를 실시간으로 모니터링하여 Expect 처리
"""
from PyQt5.QtCore import QThread, pyqtSignal, QMutex, QWaitCondition
from typing import List, Optional
import time
from model.macro_entry import MacroEntry
from model.packet_parser import ExpectMatcher
from core.logger import logger
from core.event_bus import event_bus

class MacroRunner(QThread):
    """
    매크로 실행 엔진 (Thread Based)

    QTimer 대신 QThread와 QWaitCondition을 사용하여
    UI 블로킹에 영향받지 않는 정밀한 타이밍을 보장합니다.
    """
    # Signals
    step_started = pyqtSignal(int, MacroEntry)  # index, entry
    step_completed = pyqtSignal(int, bool)      # index, success
    macro_finished = pyqtSignal()
    error_occurred = pyqtSignal(str)

    # Send Signal (외부에서 연결하여 실제 전송 수행)
    # UI 스레드와의 통신을 위해 QueuedConnection으로 동작함
    send_requested = pyqtSignal(str, bool, bool, bool) # text, hex, prefix, suffix

    def __init__(self):
        super().__init__()
        self._entries: List[MacroEntry] = []

        # 스레드 제어 동기화 객체
        self._mutex = QMutex()
        self._cond = QWaitCondition()

        # 상태 변수
        self._is_running = False
        self._is_paused = False

        # 실행 설정
        self._loop_count = 0
        self._loop_interval_ms = 0

        # Expect 처리를 위한 변수
        self._expect_matcher: Optional[ExpectMatcher] = None
        self._expect_found = False
        self._expect_cond = QWaitCondition() # Expect 대기 전용 조건 변수

        self.event_bus = event_bus
        # 데이터 수신 구독 (EventBus 사용)
        self.event_bus.subscribe("port.data_received", self._on_data_received)

    def load_macro(self, entries: List[MacroEntry]) -> None:
        """
        매크로 리스트 로드

        Args:
            entries: 실행할 매크로 항목 리스트
        """
        self._entries = entries

    def start(self, loop_count: int = 1, interval_ms: int = 0) -> None:
        """
        매크로 실행 시작 (QThread.start 오버라이드)

        Args:
            loop_count: 반복 횟수 (0=무한)
            interval_ms: 루프 간 간격 (ms)
        """
        if not self._entries:
            self.error_occurred.emit("No macro entries loaded.")
            return

        self._mutex.lock()
        self._is_running = True
        self._is_paused = False
        self._loop_count = loop_count
        self._loop_interval_ms = interval_ms
        self._mutex.unlock()

        self.event_bus.publish("macro.started")

        # QThread 시작 (run 메서드 호출)
        super().start()

    def stop(self) -> None:
        """
        매크로 실행 중지

        대기 중인 스레드를 깨우고 루프를 종료시킵니다.
        """
        self._mutex.lock()
        self._is_running = False
        self._is_paused = False
        self._cond.wakeAll() # 일반 대기 해제
        self._expect_cond.wakeAll() # Expect 대기 해제
        self._mutex.unlock()

        # 스레드 종료 대기
        self.wait()

        self.macro_finished.emit()
        self.event_bus.publish("macro.finished")

    def pause(self) -> None:
        """일시 정지"""
        self._mutex.lock()
        if self._is_running:
            self._is_paused = True
        self._mutex.unlock()

    def resume(self) -> None:
        """재개"""
        self._mutex.lock()
        if self._is_running and self._is_paused:
            self._is_paused = False
            self._cond.wakeAll() # 일시정지 대기 해제
        self._mutex.unlock()

    def request_single_send(self, command: str, is_hex: bool, prefix: bool, suffix: bool) -> None:
        """
        단일 명령 전송 요청 (프레젠터에서 호출)

        Args:
            command (str): 전송할 명령어
            is_hex (bool): HEX 형식 여부
            prefix (bool): CR 접두사 추가 여부
            suffix (bool): LF 접미사 추가 여부
        """
        self.send_requested.emit(command, is_hex, prefix, suffix)

    def _on_data_received(self, data_dict: dict) -> None:
        """
        EventBus로부터 수신된 데이터를 처리합니다.
        Expect 매칭 중이라면 매처에 데이터를 전달합니다.

        Args:
            data_dict: {'port': str, 'data': bytes}
        """
        # 실행 중이 아니거나 매처가 없으면 무시
        if not self._is_running or self._expect_matcher is None:
            return

        data = data_dict.get('data', b'')
        if not data:
            return

        self._mutex.lock()
        # 매칭 시도
        if self._expect_matcher and self._expect_matcher.match(data):
            self._expect_found = True
            self._expect_cond.wakeAll() # 대기 중인 스레드를 깨움
        self._mutex.unlock()

    def run(self) -> None:
        """
        스레드 실행 메인 루프

        Logic:
            - 설정된 Loop 횟수만큼 반복
            - 각 Entry 순차 실행
            - Pause 상태 체크 및 대기
            - Send -> Expect(Wait) -> Result 처리 -> Delay
            - UI 블로킹 없이 정밀한 타이밍 수행
        """
        current_loop = 0

        while self._check_running():
            # 1. 루프 횟수 체크 (0은 무한)
            if self._loop_count > 0 and current_loop >= self._loop_count:
                break

            current_loop += 1

            # 2. 엔트리 순차 실행
            for i, entry in enumerate(self._entries):
                # 실행 중지 체크
                if not self._check_running():
                    break

                # 일시정지 처리
                self._handle_pause()

                # 비활성화 항목 건너뛰기
                if not entry.enabled:
                    continue

                # 스텝 시작 알림
                self.step_started.emit(i, entry)
                step_success = True
                error_msg = ""

                try:
                    # 2-1. 명령 전송 (Signal -> UI Thread -> PortController)
                    self.send_requested.emit(entry.command, entry.is_hex, entry.prefix, entry.suffix)

                    # 2-2. Expect 처리 (응답 대기)
                    if entry.expect:
                        step_success = self._wait_for_expect(entry.expect, entry.timeout_ms)
                        if not step_success:
                            error_msg = f"Expect timeout: pattern '{entry.expect}' not found."

                    # 2-3. 결과 처리
                    if step_success:
                        self.step_completed.emit(i, True)
                        # 성공 시 Delay 처리 (정밀 대기)
                        delay = entry.delay_ms if entry.delay_ms > 0 else 10
                        self._interruptible_sleep(delay)
                    else:
                        # 실패 시 처리 (중단)
                        self.step_completed.emit(i, False)
                        self.error_occurred.emit(error_msg)
                        self.event_bus.publish("macro.error", error_msg)
                        self._is_running = False # 루프 중단
                        break

                except Exception as e:
                    logger.error(f"Macro execution error at index {i}: {e}")
                    self.error_occurred.emit(str(e))
                    self.event_bus.publish("macro.error", str(e))
                    self._is_running = False
                    break

            # 루프 간 간격 대기
            if self._check_running() and self._loop_interval_ms > 0:
                self._interruptible_sleep(self._loop_interval_ms)

        # 실행 종료 처리 (플래그 정리)
        self._mutex.lock()
        self._is_running = False
        self._mutex.unlock()

    def _wait_for_expect(self, pattern: str, timeout_ms: int) -> bool:
        """
        Expect 패턴 매칭을 대기합니다.

        Logic:
            - ExpectMatcher 초기화
            - EventBus를 통해 들어오는 데이터를 _on_data_received에서 매칭
            - QWaitCondition을 사용하여 timeout_ms 동안 대기
            - 매칭 성공 시 즉시 깨어나 True 반환, 타임아웃 시 False 반환

        Args:
            pattern: 매칭할 패턴
            timeout_ms: 대기 시간 (ms)

        Returns:
            bool: 매칭 성공 여부
        """
        self._mutex.lock()

        # 매처 초기화 (정규식 여부는 자동 감지하도록 ExpectMatcher 구현됨)
        self._expect_matcher = ExpectMatcher(pattern, is_regex=True)
        self._expect_found = False

        # 타임아웃 계산을 위한 시작 시간
        start_time = time.monotonic()
        remaining_time = timeout_ms

        # 대기 루프
        while self._is_running and not self._expect_found:
            if remaining_time <= 0:
                break

            # 지정된 시간만큼 대기 (조건 변수가 시그널을 받거나 타임아웃될 때까지)
            if not self._expect_cond.wait(self._mutex, int(remaining_time)):
                # 타임아웃으로 깨어남
                break

            # 깨어난 후 남은 시간 재계산 (Spurious wakeup 대비)
            elapsed = (time.monotonic() - start_time) * 1000
            remaining_time = timeout_ms - elapsed

        success = self._expect_found

        # 정리
        self._expect_matcher = None
        self._expect_found = False

        self._mutex.unlock()
        return success

    def _check_running(self) -> bool:
        """실행 중인지 확인 (Thread-safe)"""
        self._mutex.lock()
        running = self._is_running
        self._mutex.unlock()
        return running

    def _handle_pause(self) -> None:
        """일시 정지 상태일 경우 대기 (Thread-safe)"""
        self._mutex.lock()
        while self._is_paused and self._is_running:
            # resume()이 호출되어 wakeAll()할 때까지 대기
            self._cond.wait(self._mutex)
        self._mutex.unlock()

    def _interruptible_sleep(self, ms: int) -> None:
        """
        중단 가능한 Sleep

        QWaitCondition.wait()를 사용하여 지정된 시간만큼 대기하되,
        stop()이나 외부 시그널에 의해 즉시 깨어날 수 있음.

        Args:
            ms: 대기 시간 (밀리초)
        """
        self._mutex.lock()
        if self._is_running:
            # 타임아웃(ms) 동안 대기. wakeAll() 호출 시 즉시 리턴.
            self._cond.wait(self._mutex, ms)
        self._mutex.unlock()
