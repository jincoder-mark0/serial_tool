"""
매크로 Presenter.

MacroPanel의 사용자 요청과 MacroRunner/MacroScriptManager를 중재합니다. 파일 I/O와
load QThread 생명주기는 Model이 소유하며 두 의존성은 composition root가 명시적으로
주입합니다.
"""
from typing import List, Tuple

from PyQt5.QtCore import QObject, pyqtSignal

from common.constants import MIN_MACRO_DELAY_MS
from common.dtos import (
    MacroEntry,
    MacroErrorEvent,
    MacroExecutionRequest,
    MacroScriptData,
    MacroStepEvent,
    ManualCommand,
)
from core.logger import logger
from model.macro_runner import MacroRunner
from model.macro_script_manager import MacroScriptManager
from view.managers.language_manager import language_manager
from view.panels.macro_panel import MacroPanel


class MacroPresenter(QObject):
    """매크로 실행 UI와 실행/스크립트 Model을 연결합니다."""

    broadcast_changed = pyqtSignal(bool)

    def __init__(
        self,
        panel: MacroPanel,
        runner: MacroRunner,
        script_manager: MacroScriptManager,
    ) -> None:
        super().__init__()
        self.panel = panel
        self.runner = runner
        self.script_manager = script_manager

        self.panel.repeat_start_requested.connect(self.on_repeat_start)
        self.panel.repeat_stop_requested.connect(self.on_repeat_stop)
        self.panel.repeat_pause_requested.connect(self.on_repeat_pause)
        self.panel.script_save_requested.connect(self.on_script_save)
        self.panel.script_load_requested.connect(self.on_script_load)
        self.panel.send_row_requested.connect(self.on_single_send_requested)
        self.panel.broadcast_changed.connect(self.broadcast_changed.emit)

        self.script_manager.script_loaded.connect(self._on_load_success)
        self.script_manager.load_failed.connect(self._on_load_failed)
        self.script_manager.save_succeeded.connect(self._on_save_success)
        self.script_manager.save_failed.connect(self._on_save_failed)

        self.runner.step_started.connect(self.on_step_started)
        self.runner.step_completed.connect(self.on_step_completed)
        self.runner.macro_finished.connect(self.on_macro_finished)
        self.runner.error_occurred.connect(self.on_error)
        self.runner.loop_progress.connect(self.on_loop_progress)

    def set_enabled(self, enabled: bool) -> None:
        self.panel.set_controls_enabled(enabled)

    def is_broadcast_enabled(self) -> bool:
        return self.panel.is_broadcast_enabled()

    def on_script_save(self, script_data: MacroScriptData) -> None:
        self.script_manager.save_script(script_data)

    def _on_save_success(self, _file_path: str) -> None:
        self.panel.show_info(
            language_manager.get_text("macro_panel_title_save_success"),
            language_manager.get_text("macro_panel_msg_save_success"),
        )

    def _on_save_failed(self, error_msg: str) -> None:
        self.panel.show_error(
            language_manager.get_text("macro_panel_title_save_error"),
            language_manager.get_text("macro_panel_msg_save_error").format(error_msg),
        )

    def on_script_load(self, file_path: str) -> None:
        self.script_manager.request_load(file_path)

    def _on_load_success(self, script_data: MacroScriptData) -> None:
        self.panel.apply_state(script_data.data)

    def _on_load_failed(self, error_msg: str) -> None:
        self.panel.show_error(
            language_manager.get_text("macro_panel_title_load_error"),
            language_manager.get_text("macro_panel_msg_load_error").format(error_msg),
        )

    def on_repeat_start(self, request: MacroExecutionRequest) -> None:
        indices = request.indices
        if not indices:
            return

        all_entries = self.panel.get_macro_entries()
        execution_plan: List[Tuple[int, MacroEntry]] = []

        for index, entry in enumerate(all_entries):
            if index not in indices:
                continue
            if entry.delay_ms is None or entry.delay_ms < MIN_MACRO_DELAY_MS:
                entry.delay_ms = MIN_MACRO_DELAY_MS
            execution_plan.append((index, entry))

        if not execution_plan:
            return

        option = request.option
        self.runner.load_macro(execution_plan)
        self.runner.start(
            loop_count=option.max_runs,
            interval_ms=option.interval_ms,
            broadcast_enabled=option.broadcast_enabled,
            stop_on_error=option.stop_on_error,
        )
        self.panel.set_running_state(True, is_repeat=True)

    def on_repeat_stop(self) -> None:
        self.runner.stop()

    def on_repeat_pause(self) -> None:
        if self.runner.is_paused():
            self.runner.resume()
        else:
            self.runner.pause()

    def on_single_send_requested(self, _row_index: int, entry: MacroEntry) -> None:
        if not entry:
            return

        self.runner.send_single_command(
            ManualCommand(
                command=entry.command,
                hex_mode=entry.hex_mode,
                prefix_enabled=entry.prefix_enabled,
                suffix_enabled=entry.suffix_enabled,
                broadcast_enabled=False,
            )
        )

    def on_step_started(self, event: MacroStepEvent) -> None:
        self.panel.set_current_row(event.index)

    def on_step_completed(self, _event: MacroStepEvent) -> None:
        return

    def on_macro_finished(self) -> None:
        self.panel.set_running_state(False)
        self.panel.set_current_row(-1)

    def on_loop_progress(self, current: int, total: int) -> None:
        self.panel.update_auto_count(current, total)

    def on_error(self, event: MacroErrorEvent) -> None:
        logger.error(f"Macro Error: {event.message}")
        self.panel.set_running_state(False)
        self.panel.set_current_row(-1)
