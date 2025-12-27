"""
매크로 실행 엔진 모듈

사용자가 정의한 Command 시퀀스를 별도 스레드에서 순차적으로 실행하는 엔진입니다.

## WHY
* UI 스레드 블로킹 없는 장시간 매크로 실행 보장
* 1ms 단위의 정밀한 타이밍 제어 필요 (QTimer의 정밀도 한계 극복)
* 실행 중 즉각적인 일시정지(Pause) 및 중단(Stop) 지원 필요
* 특정 응답 대기(Expect) 기능 구현을 위한 비동기 수신 처리 필요

## WHAT
* QThread 기반의 독립 실행 환경 제공
* 매크로 항목(MacroEntry) 순차 실행 및 루프 제어
* Expect 기능(정규식 기반 응답 대기) 및 타임아웃 처리
* 에러 발생 시 처리 정책(중단/무시) 지원

## HOW
* QThread, QWaitCondition, QMutex를 사용한 정밀 제어 및 스레드 동기화
* EventBus를 통해 수신 데이터를 구독하여 Expect 패턴 매칭
* DTO를 통한 데이터 교환 및 에러 보고
* (RowIndex, Entry) 튜플 구조를 사용하여 UI 필터링 상황에서도 정확한 행 추적
"""
import time
from typing import List, Optional, Tuple

from PyQt5.QtCore import QThread, pyqtSignal, QMutex, QWaitCondition

from common.dtos import (
    MacroEntry,
    ManualCommand,
    MacroStepEvent,
    PortDataEvent,
    MacroErrorEvent
)
from common.constants import EventTopics
from model.packet_parser import ExpectMatcher
from core.logger import logger
from core.event_bus import event_bus


class MacroRunner(QThread):
    """
    매크로 실행 엔진 클래스

    QTimer 대신 QThread와 QWaitCondition을 사용하여 UI 프리징을 방지하고
    정밀한 타이밍 제어를 보장합니다.
    """

    # -------------------------------------------------------------------------
    # Signals (DTO 기반)
    # -------------------------------------------------------------------------
    # 실행 단계별 이벤트 (index는 UI의 원본 Row Index를 의미함)
    step_started = pyqtSignal(object)    # MacroStepEvent
    step_completed = pyqtSignal(object)  # MacroStepEvent
    macro_finished = pyqtSignal()
    error_occurred = pyqtSignal(object)  # MacroErrorEvent

    # 실제 전송 요청 시그널 (ConnectionController 등으로 연결)
    send_requested = pyqtSignal(object)  # ManualCommand

    # 반복 진행 상태 알림 (현재 횟수, 총 횟수)
    loop_progress = pyqtSignal(int, int)

    def __init__(self) -> None:
        """
        MacroRunner 초기화 및 상태 변수 설정

        Logic:
            - 스레드 동기화 객체(Mutex, WaitCondition) 초기화
            - 실행 상태 플래그 초기화
            - EventBus 구독 설정 (데이터 수신 감지용)
        """
        super().__init__()
        
        # (Row Index, Entry DTO) 튜플 리스트로 관리하여 UI 위치 추적 보장
        self._entries: List[Tuple[int, MacroEntry]] = []

        # 스레드 동기화 객체
        self._mutex = QMutex()
        self._cond = QWaitCondition()        # 일반 대기 (Sleep/Pause)
        self._expect_cond = QWaitCondition() # Expect 대기 전용

        # 실행 제어 플래그
        self._is_running = False
        self._is_paused = False
        
        # 실행 옵션
        self._loop_count = 0
        self._loop_interval_ms = 0
        self.broadcast_enabled = False
        self.stop_on_error = True

        # Expect 처리 변수
        self._expect_matcher: Optional[ExpectMatcher] = None
        self._expect_found = False

        self.event_bus = event_bus
        # 데이터 수신 이벤트 구독 (Expect 매칭용)
        self.event_bus.subscribe(EventTopics.PORT_DATA_RECEIVED, self._on_data_received)

    def load_macro(self, entries: List[Tuple[int, MacroEntry]]) -> None:
        """
        실행할 매크로 리스트를 로드합니다.

        Args:
            entries: (원본 행 번호, 매크로 항목) 튜플의 리스트.
        """
        self._entries = entries

    def start(self, loop_count: int = 1, interval_ms: int = 0, 
              broadcast_enabled: bool = False, stop_on_error: bool = True) -> None:
        """
        매크로 실행을 시작합니다.

        Logic:
            1. 매크로 엔트리 존재 여부 확인
            2. Mutex를 사용하여 실행 플래그 및 옵션 설정
            3. 시작 이벤트 발행 (`macro.started`)
            4. QThread 시작 (`run` 메서드 호출)

        Args:
            loop_count (int): 반복 횟수 (0=무한). 기본값 1.
            interval_ms (int): 루프 간 대기 시간 (ms). 기본값 0.
            broadcast_enabled (bool): 브로드캐스트 모드 여부.
            stop_on_error (bool): 에러 발생 시 중단 여부.
        """
        if not self._entries:
            # 에러 DTO 생성 및 전송
            error_event = MacroErrorEvent(message="No macro entries loaded.")
            self.error_occurred.emit(error_event)
            return

        self._mutex.lock()
        self._is_running = True
        self._is_paused = False
        self._loop_count = loop_count
        self._loop_interval_ms = interval_ms
        self.broadcast_enabled = broadcast_enabled
        self.stop_on_error = stop_on_error
        self._mutex.unlock()

        self.event_bus.publish(EventTopics.MACRO_STARTED)

        # QThread의 start 호출 -> run() 실행
        super().start()

    def stop(self) -> None:
        """
        매크로 실행을 중단합니다.

        Logic:
            1. 실행 플래그 해제 및 일시정지 해제
            2. 대기 중인 모든 조건 변수(`_cond`, `_expect_cond`)를 깨움
            3. 스레드가 완전히 종료될 때까지 대기 (`wait`)
            4. 종료 이벤트 발행
        """
        self._stop_internal(reason="User stopped macro")
        
        # 스레드 종료 대기 (블로킹)
        self.wait()

        self.macro_finished.emit()
        self.event_bus.publish(EventTopics.MACRO_FINISHED)

    def _stop_internal(self, reason: str = "") -> None:
        """
        내부적인 중단 처리 (스레드 내부 또는 강제 종료 시 사용)

        Args:
            reason (str): 중단 사유 (로깅용).
        """
        self._mutex.lock()
        if self._is_running:
            self._is_running = False
            self._is_paused = False
            self._cond.wakeAll()
            self._expect_cond.wakeAll()
            if reason:
                logger.info(f"Macro stopping: {reason}")
        self._mutex.unlock()

    def pause(self) -> None:
        """
        실행을 일시 정지합니다.
        """
        self._mutex.lock()
        if self._is_running:
            self._is_paused = True
        self._mutex.unlock()

    def resume(self) -> None:
        """
        일시 정지된 실행을 재개합니다.

        Logic:
            - 일시정지 플래그 해제
            - 대기 중인 스레드를 깨움 (`wakeAll`)
        """
        self._mutex.lock()
        if self._is_running and self._is_paused:
            self._is_paused = False
            self._cond.wakeAll()
        self._mutex.unlock()

    def send_single_command(self, command: ManualCommand) -> None:
        """
        단일 명령 전송을 요청합니다 (Presenter에서 사용).

        Args:
            command (ManualCommand): 전송할 명령어 DTO.
        """
        # DTO를 그대로 시그널로 전달
        self.send_requested.emit(command)

    def _on_data_received(self, event: PortDataEvent) -> None:
        """
        수신 데이터 처리 핸들러 (EventBus 콜백).

        Logic:
            1. DTO 타입 검증
            2. Mutex 잠금으로 스레드 안전성 확보
            3. 실행 중이 아니거나 Matcher가 없으면 무시
            4. Matcher에 데이터 전달하여 매칭 시도
            5. 매칭 성공 시 `_expect_found` 플래그 설정 및 대기 스레드 깨움

        Args:
            event (PortDataEvent): 수신 데이터 DTO.
        """
        # [DTO] 타입 검증
        if not isinstance(event, PortDataEvent):
            return

        data = event.data
        if not data:
            return

        self._mutex.lock()
        try:
            # 실행 중이고 매처가 있을 때만 처리
            if self._is_running and self._expect_matcher:
                if self._expect_matcher.match(data):
                    self._expect_found = True
                    self._expect_cond.wakeAll()
        finally:
            self._mutex.unlock()

    def run(self) -> None:
        """
        스레드 실행 메인 루프 (QThread 진입점).

        Logic:
            1. 루프 횟수만큼 전체 시퀀스 반복
            2. 각 매크로 항목(`MacroEntry`) 순차 실행
            3. 일시정지 상태 확인 및 대기
            4. 명령 전송 -> Expect 대기 -> 지연 시간 대기
            5. 에러 또는 중단 요청 시 루프 탈출
        """
        current_loop = 0

        while self._check_running():
            # 1. 루프 횟수 체크 (0은 무한 반복)
            if 0 < self._loop_count <= current_loop:
                break

            current_loop += 1
            # 반복 진행 상황 알림 (UI 업데이트)
            self.loop_progress.emit(current_loop, self._loop_count)

            # 2. 엔트리 순차 실행 (row_index와 entry unpacking)
            for row_idx, entry in self._entries:
                # 실행 중지 확인
                if not self._check_running():
                    break

                # 일시정지 처리
                self._handle_pause()

                # 비활성화 항목 건너뛰기
                if not entry.enabled:
                    continue

                # DTO 이벤트 발생 (Started) - 원본 Row Index 사용
                self.step_started.emit(MacroStepEvent(index=row_idx, entry=entry, type="started"))

                step_success = True
                error_msg = ""

                try:
                    # DTO 생성
                    manual_command = ManualCommand(
                        command=entry.command,
                        hex_mode=entry.hex_mode,
                        prefix_enabled=entry.prefix_enabled,
                        suffix_enabled=entry.suffix_enabled,
                        broadcast_enabled=self.broadcast_enabled
                    )
                    
                    # 2-1. 명령 전송 요청 (Signal)
                    self.send_requested.emit(manual_command)

                    # 2-2. Expect 처리 (응답 대기)
                    if entry.expect:
                        # 브로드캐스트 모드에서는 동기화 문제로 인해 Expect를 무시
                        if self.broadcast_enabled:
                            logger.debug(f"Row {row_idx}: Expect pattern ignored in broadcast mode.")
                            step_success = True
                        else:
                            step_success = self._wait_for_expect(entry.expect, entry.timeout_ms)
                            if not step_success:
                                error_msg = f"Expect timeout: pattern '{entry.expect}' not found."

                    # 2-3. 결과 처리 및 지연
                    if step_success:
                        self.step_completed.emit(MacroStepEvent(index=row_idx, success=True, type="completed"))
                        # 최소 10ms 지연 보장 (UI 프리징 방지)
                        delay = entry.delay_ms if entry.delay_ms > 0 else 10
                        self._interruptible_sleep(delay)
                    else:
                        # 실패 처리
                        self.step_completed.emit(MacroStepEvent(index=row_idx, success=False, type="completed"))

                        # [DTO] 에러 이벤트 생성 및 발행
                        error_event = MacroErrorEvent(message=error_msg, row_index=row_idx)
                        self.error_occurred.emit(error_event)
                        self.event_bus.publish(EventTopics.MACRO_ERROR, error_event)

                        # 에러 발생 시 처리 정책 확인
                        if self.stop_on_error:
                            logger.warning(f"Macro stopped due to error at row {row_idx}")
                            self._stop_internal()
                            break
                        else:
                            logger.info(f"Macro error at row {row_idx}, but continuing (stop_on_error=False)")
                            # 에러 후에도 최소한의 안전 지연
                            self._interruptible_sleep(100)

                except Exception as e:
                    # 예상치 못한 시스템 에러는 무조건 중단
                    logger.error(f"Critical macro execution error at row {row_idx}: {e}")

                    # [DTO] 에러 이벤트 생성 및 발행
                    error_event = MacroErrorEvent(message=str(e), row_index=row_idx)
                    self.error_occurred.emit(error_event)
                    self.event_bus.publish(EventTopics.MACRO_ERROR, error_event)

                    self._stop_internal()
                    break

            # 루프 간 간격 대기
            if self._check_running() and self._loop_interval_ms > 0:
                self._interruptible_sleep(self._loop_interval_ms)

        # 실행 종료 처리
        self._stop_internal()
        
        # 완료 시그널 방출
        self.macro_finished.emit()

    def _check_running(self) -> bool:
        """
        실행 중인지 확인합니다. (Thread-safe)

        Returns:
            bool: 실행 중이면 True.
        """
        self._mutex.lock()
        running = self._is_running
        self._mutex.unlock()
        return running

    def _handle_pause(self) -> None:
        """일시 정지 상태일 경우 대기합니다."""
        self._mutex.lock()
        try:
            while self._is_paused and self._is_running:
                # resume()이 호출되어 wakeAll()할 때까지 대기
                self._cond.wait(self._mutex)
        finally:
            self._mutex.unlock()

    def _interruptible_sleep(self, ms: int) -> None:
        """
        중단 가능한 Sleep

        QWaitCondition.wait()를 사용하여 지정된 시간만큼 대기하되,
        stop()이나 외부 시그널에 의해 즉시 깨어날 수 있습니다.

        Args:
            ms (int): 대기 시간 (밀리초).
        """
        self._mutex.lock()
        try:
            if self._is_running:
                # 타임아웃(ms) 동안 대기
                self._cond.wait(self._mutex, ms)
        finally:
            self._mutex.unlock()

    def _wait_for_expect(self, pattern: str, timeout_ms: int) -> bool:
        """
        Expect 패턴 매칭 대기

        Logic:
            1. ExpectMatcher 초기화 (EventBus 리스너가 사용할 수 있도록 설정)
            2. 지정된 시간(`timeout_ms`) 동안 조건 변수 대기
            3. 데이터 수신 시 리스너가 조건 변수를 깨움(`wakeAll`)
            4. 매칭 성공 또는 타임아웃 시 결과 반환

        Args:
            pattern (str): 매칭할 정규식 또는 문자열 패턴.
            timeout_ms (int): 대기 시간 제한 (ms).

        Returns:
            bool: 매칭 성공 여부 (True=성공, False=타임아웃).
        """
        self._mutex.lock()

        # Matcher 설정
        self._expect_matcher = ExpectMatcher(pattern, regex_enabled=True)
        self._expect_found = False

        start_time = time.monotonic()
        remaining_time = timeout_ms

        try:
            while self._is_running and not self._expect_found:
                if remaining_time <= 0:
                    break

                # Mutex를 잠시 풀고 대기, 신호가 오거나 타임아웃되면 다시 잠금
                if not self._expect_cond.wait(self._mutex, int(remaining_time)):
                    # 타임아웃 발생
                    break

                # Spurious Wakeup 대비 남은 시간 재계산
                elapsed = (time.monotonic() - start_time) * 1000
                remaining_time = timeout_ms - elapsed
        finally:
            # 상태 정리
            success = self._expect_found
            self._expect_matcher = None
            self._expect_found = False
            self._mutex.unlock()

        return success