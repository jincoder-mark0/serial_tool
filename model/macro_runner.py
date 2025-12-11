from PyQt5.QtCore import QObject, pyqtSignal, QTimer
from typing import List, Optional
import re
from model.macro_entry import MacroEntry
from core.logger import logger

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
        
        self._start_loop()

    def stop(self) -> None:
        """매크로 실행 중지"""
        self._is_running = False
        self._is_paused = False
        self._step_timer.stop()
        self._loop_timer.stop()
        self.macro_finished.emit()

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

    def _execute_next_step(self) -> None:
        """다음 스텝 실행"""
        if not self._is_running or self._is_paused:
            return

        # 유효한 항목 찾기
        while self._current_index < len(self._entries):
            entry = self._entries[self._current_index]
            if entry.enabled:
                break
            self._current_index += 1
        
        # 모든 항목 실행 완료
        if self._current_index >= len(self._entries):
            if self._loop_interval_ms > 0:
                self._loop_timer.start(self._loop_interval_ms)
            else:
                self._start_loop() # 즉시 다음 루프
            return

        entry = self._entries[self._current_index]
        self.step_started.emit(self._current_index, entry)

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
        self.stop()
