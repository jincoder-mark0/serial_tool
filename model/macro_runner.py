"""
매크로 실행 엔진 모듈

Command 시퀀스를 별도 QThread에서 순차 실행하며 Pause/Stop/Expect/반복 실행을 지원합니다.
단계 이벤트 타입은 common.enums.MacroStepType을 정본으로 사용합니다.
"""
import time
from typing import Callable, List, Optional, Tuple

from PyQt5.QtCore import QMutex, QThread, QWaitCondition, pyqtSignal

from common.constants import EventTopics
from common.dtos import (
    MacroEntry,
    MacroErrorEvent,
    MacroSendResult,
    MacroStepEvent,
    ManualCommand,
    PortDataEvent,
)
from common.enums import MacroStepType
from core.event_bus import event_bus
from core.logger import logger
from model.packet_parser import ExpectMatcher


class MacroRunner(QThread):
    """매크로 실행 순서와 스레드 동기화를 담당합니다."""

    step_started = pyqtSignal(object)
    step_completed = pyqtSignal(object)
    macro_finished = pyqtSignal()
    error_occurred = pyqtSignal(object)
    send_requested = pyqtSignal(object)
    loop_progress = pyqtSignal(int, int)

    def __init__(self) -> None:
        super().__init__()
        self._entries: List[Tuple[int, MacroEntry]] = []
        self._mutex = QMutex()
        self._cond = QWaitCondition()
        self._expect_cond = QWaitCondition()
        self._is_running = False
        self._is_paused = False
        self._loop_count = 0
        self._loop_interval_ms = 0
        self.broadcast_enabled = False
        self.stop_on_error = True
        self._expect_matcher: Optional[ExpectMatcher] = None
        self._expect_found = False
        self.event_bus = event_bus
        self.event_bus.subscribe(EventTopics.PORT_DATA_RECEIVED, self._on_data_received)
        self._send_handler: Optional[Callable[[ManualCommand], MacroSendResult]] = None

    def set_send_handler(
        self, handler: Optional[Callable[[ManualCommand], MacroSendResult]]
    ) -> None:
        self._send_handler = handler

    def load_macro(self, entries: List[Tuple[int, MacroEntry] | MacroEntry]) -> None:
        self._entries = [
            item if isinstance(item, tuple) else (index, item)
            for index, item in enumerate(entries)
        ]

    def start(
        self,
        loop_count: int = 1,
        interval_ms: int = 0,
        broadcast_enabled: bool = False,
        stop_on_error: bool = True,
    ) -> None:
        if not self._entries:
            self.error_occurred.emit(MacroErrorEvent(message="No macro entries loaded."))
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
        super().start()

    def stop(self) -> None:
        self._stop_internal(reason="User stopped macro")
        self.wait()

    def _stop_internal(self, reason: str = "") -> None:
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
        self._mutex.lock()
        if self._is_running:
            self._is_paused = True
        self._mutex.unlock()

    def is_paused(self) -> bool:
        self._mutex.lock()
        paused = self._is_paused
        self._mutex.unlock()
        return paused

    def resume(self) -> None:
        self._mutex.lock()
        if self._is_running and self._is_paused:
            self._is_paused = False
            self._cond.wakeAll()
        self._mutex.unlock()

    def _send(self, command: ManualCommand) -> MacroSendResult:
        handler = self._send_handler
        if handler is None:
            return MacroSendResult(False, "No send handler is registered.")
        try:
            return handler(command)
        except Exception as exc:
            logger.error(f"Send handler raised: {exc}", exc_info=True)
            return MacroSendResult(False, f"Send handler error: {exc}")

    def send_single_command(self, command: ManualCommand) -> None:
        self.send_requested.emit(command)

    def _on_data_received(self, event: PortDataEvent) -> None:
        if not isinstance(event, PortDataEvent) or not event.data:
            return

        self._mutex.lock()
        try:
            if self._is_running and self._expect_matcher and self._expect_matcher.match(event.data):
                self._expect_found = True
                self._expect_cond.wakeAll()
        finally:
            self._mutex.unlock()

    def run(self) -> None:
        current_loop = 0

        while self._check_running():
            if 0 < self._loop_count <= current_loop:
                break

            current_loop += 1
            self.loop_progress.emit(current_loop, self._loop_count)

            for row_idx, entry in self._entries:
                if not self._check_running():
                    break

                self._handle_pause()
                if not entry.enabled:
                    continue

                self.step_started.emit(
                    MacroStepEvent(
                        index=row_idx,
                        entry=entry,
                        type=MacroStepType.STARTED.value,
                    )
                )

                step_success = True
                error_msg = ""

                try:
                    manual_command = ManualCommand(
                        command=entry.command,
                        hex_mode=entry.hex_mode,
                        prefix_enabled=entry.prefix_enabled,
                        suffix_enabled=entry.suffix_enabled,
                        broadcast_enabled=self.broadcast_enabled,
                    )
                    send_result = self._send(manual_command)
                    if not send_result.success:
                        step_success = False
                        error_msg = send_result.message or "Send failed."

                    if step_success and entry.expect:
                        if self.broadcast_enabled:
                            logger.debug(
                                f"Row {row_idx}: Expect pattern ignored in broadcast mode."
                            )
                        else:
                            step_success = self._wait_for_expect(entry.expect, entry.timeout_ms)
                            if not step_success:
                                error_msg = f"Expect timeout: pattern '{entry.expect}' not found."

                    self.step_completed.emit(
                        MacroStepEvent(
                            index=row_idx,
                            success=step_success,
                            type=MacroStepType.COMPLETED.value,
                        )
                    )

                    if step_success:
                        delay = entry.delay_ms if entry.delay_ms > 0 else 10
                        self._interruptible_sleep(delay)
                    else:
                        error_event = MacroErrorEvent(message=error_msg, row_index=row_idx)
                        self.error_occurred.emit(error_event)
                        self.event_bus.publish(EventTopics.MACRO_ERROR, error_event)
                        if self.stop_on_error:
                            logger.warning(f"Macro stopped due to error at row {row_idx}")
                            self._stop_internal()
                            break
                        logger.info(
                            f"Macro error at row {row_idx}, but continuing (stop_on_error=False)"
                        )
                        self._interruptible_sleep(100)

                except Exception as exc:
                    logger.error(f"Critical macro execution error at row {row_idx}: {exc}")
                    error_event = MacroErrorEvent(message=str(exc), row_index=row_idx)
                    self.error_occurred.emit(error_event)
                    self.event_bus.publish(EventTopics.MACRO_ERROR, error_event)
                    self._stop_internal()
                    break

            if self._check_running() and self._loop_interval_ms > 0:
                self._interruptible_sleep(self._loop_interval_ms)

        self._stop_internal()
        self.macro_finished.emit()
        self.event_bus.publish(EventTopics.MACRO_FINISHED)

    def _check_running(self) -> bool:
        self._mutex.lock()
        running = self._is_running
        self._mutex.unlock()
        return running

    def _handle_pause(self) -> None:
        self._mutex.lock()
        try:
            while self._is_paused and self._is_running:
                self._cond.wait(self._mutex)
        finally:
            self._mutex.unlock()

    def _interruptible_sleep(self, ms: int) -> None:
        self._mutex.lock()
        try:
            if self._is_running:
                self._cond.wait(self._mutex, ms)
        finally:
            self._mutex.unlock()

    def _wait_for_expect(self, pattern: str, timeout_ms: int) -> bool:
        self._mutex.lock()
        self._expect_matcher = ExpectMatcher(pattern, regex_enabled=True)
        self._expect_found = False
        start_time = time.monotonic()
        remaining_time = timeout_ms

        try:
            while self._is_running and not self._expect_found:
                if remaining_time <= 0:
                    break
                if not self._expect_cond.wait(self._mutex, int(remaining_time)):
                    break
                elapsed = (time.monotonic() - start_time) * 1000
                remaining_time = timeout_ms - elapsed
        finally:
            success = self._expect_found
            self._expect_matcher = None
            self._expect_found = False
            self._mutex.unlock()

        return success
