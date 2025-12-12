"""
매크로 실행 엔진 모듈

이 모듈은 사용자가 정의한 명령어 시퀀스를 자동으로 실행하는 매크로 엔진을 제공합니다.

## WHY
* 반복적인 명령어 입력 작업을 자동화하여 사용자 편의성 향상
* 복잡한 테스트 시나리오를 스크립트로 저장하고 재실행 가능
* 일정한 간격으로 명령어를 반복 전송하여 디바이스 테스트 자동화

## WHAT
* 매크로 항목(MacroEntry) 리스트를 순차적으로 실행
* 각 항목의 지연 시간(delay), 반복 횟수, 간격 제어
* 실행 중 일시정지/재개/중지 기능
* 실행 상태를 시그널로 외부에 전달

## HOW
* QTimer 기반 비동기 실행으로 UI 블로킹 방지
* 상태 머신 패턴으로 실행 흐름 관리
* PyQt 시그널/슬롯으로 View와 느슨한 결합 유지
"""
from PyQt5.QtCore import QObject, pyqtSignal, QTimer
from typing import List
from model.macro_entry import MacroEntry
from core.logger import logger
from core.event_bus import event_bus

class MacroRunner(QObject):
    """
    매크로 실행 엔진 (상태 머신)
    """
    # Signals
    step_started = pyqtSignal(int, MacroEntry)  # index, entry
    step_completed = pyqtSignal(int, bool)      # index, success
    macro_finished = pyqtSignal()
    error_occurred = pyqtSignal(str)

    # Send Signal (외부에서 연결하여 실제 전송 수행)
    send_requested = pyqtSignal(str, bool, bool, bool) # text, hex, prefix, suffix

    def __init__(self):
        super().__init__()
        self._entries: List[MacroEntry] = []
        self._current_index = 0
        self._is_running = False
        self._is_paused = False

        # 타이머
        self._step_timer = QTimer()
        self._step_timer.setSingleShot(True)
        self._step_timer.timeout.connect(self._execute_next_step)

        # 반복 실행 관련
        self._loop_count = 0
        self._current_loop = 0
        self._loop_interval_ms = 0
        self._loop_timer = QTimer()
        self._loop_timer.setSingleShot(True)
        self._loop_timer.timeout.connect(self._start_loop)

        self.event_bus = event_bus

    def load_macro(self, entries: List[MacroEntry]) -> None:
        """매크로 리스트 로드"""
        self._entries = entries

    def start(self, loop_count: int = 1, interval_ms: int = 0) -> None:
        """매크로 실행 시작"""
        if not self._entries:
            self.error_occurred.emit("No macro entries loaded.")
            return

        self._is_running = True
        self._is_paused = False
        self._loop_count = loop_count
        self._current_loop = 0
        self._loop_interval_ms = interval_ms

        self.event_bus.publish("macro.started")
        self._start_loop()

    def stop(self) -> None:
        """매크로 실행 중지"""
        self._is_running = False
        self._is_paused = False
        self._step_timer.stop()
        self._loop_timer.stop()
        self.macro_finished.emit()
        self.event_bus.publish("macro.finished")

    def pause(self) -> None:
        """일시 정지"""
        if self._is_running:
            self._is_paused = True
            self._step_timer.stop()
            self._loop_timer.stop()

    def resume(self) -> None:
        """재개"""
        if self._is_running and self._is_paused:
            self._is_paused = False
            self._execute_next_step()

    def _start_loop(self) -> None:
        """새로운 루프 시작"""
        if not self._is_running:
            return

        if self._loop_count > 0 and self._current_loop >= self._loop_count:
            self.stop()
            return

        self._current_loop += 1
        self._current_index = 0
        self._execute_next_step()

    def request_single_send(self, command: str, is_hex: bool, prefix: bool, suffix: bool) -> None:
        """
        단일 명령 전송 요청 (프레젠터에서 호출)

        프레젠터가 모델의 시그널을 직접 발생시키지 않고,
        이 메서드를 통해 전송을 요청하도록 캡슐화를 개선합니다.

        Args:
            command (str): 전송할 명령어
            is_hex (bool): HEX 형식 여부
            prefix (bool): CR 접두사 추가 여부
            suffix (bool): LF 접미사 추가 여부
        """
        self.send_requested.emit(command, is_hex, prefix, suffix)


    def _execute_next_step(self) -> None:
        """
        다음 스텝 실행

        Logic:
            - 실행 가능 상태 확인 (running, paused)
            - 비활성화된 항목은 건너뛰고 다음 유효한 항목 탐색
            - 모든 항목 완료 시 루프 간격에 따라 다음 루프 예약 또는 즉시 실행
            - 현재 항목의 명령어를 send_requested 시그널로 전송
            - Expect 패턴이 있으면 대기 상태로 전환 (향후 구현)
            - 성공 시 지연 시간 후 다음 스텝 예약
        """
        if not self._is_running or self._is_paused:
            return

        # 유효한 항목 찾기 (비활성화된 항목 건너뛰기)
        while self._current_index < len(self._entries):
            entry = self._entries[self._current_index]
            if entry.enabled:
                break
            self._current_index += 1

        # 모든 항목 실행 완료
        if self._current_index >= len(self._entries):
            if self._loop_interval_ms > 0:
                # 간격을 두고 다음 루프 시작
                self._loop_timer.start(self._loop_interval_ms)
            else:
                # 즉시 다음 루프 시작
                self._start_loop()
            return

        entry = self._entries[self._current_index]
        self.step_started.emit(self._current_index, entry)
       # self.event_bus.publish("macro.step_started", {'index': self._current_index, 'entry': entry}) # Optional

        # 명령 전송
        try:
            self.send_requested.emit(entry.command, entry.is_hex, entry.prefix, entry.suffix)

            # Expect 처리 (구조만 마련)
            if entry.expect:
                # TODO: Expect 매칭을 위한 대기 상태로 전환
                # 1. RX 데이터 모니터링 시작
                # 2. 타임아웃 타이머 설정
                # 3. 매칭 성공 시 _on_step_success 호출
                # 4. 타임아웃 시 _on_step_failure 호출
                # 현재는 임시로 Delay 처리로 넘어감
                pass

            # 성공 처리 및 다음 스텝 예약
            self._on_step_success(entry)

        except Exception as e:
            logger.error(f"Macro execution error: {e}")
            self.error_occurred.emit(str(e))
            self.event_bus.publish("macro.error", str(e))
            self.stop()

    def _on_step_success(self, entry: MacroEntry) -> None:
        """스텝 성공 처리 및 다음 스텝 예약"""
        self.step_completed.emit(self._current_index, True)
        self._current_index += 1

        delay = entry.delay_ms if entry.delay_ms > 0 else 10 # 최소 딜레이
        self._step_timer.start(delay)

    def _on_step_failure(self, error_msg: str) -> None:
        """스텝 실패 처리"""
        self.error_occurred.emit(error_msg)
        self.event_bus.publish("macro.error", error_msg)
        self.stop()
