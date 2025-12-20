"""
매크로 프레젠터 모듈

매크로 실행 및 관리를 담당하는 Presenter입니다.

## WHY
* 매크로 UI 이벤트와 실행 엔진(Model)의 분리
* 파일 I/O(저장/로드)와 실행 로직의 조율
* 대용량 파일 로딩 시 UI 반응성 확보

## WHAT
* MacroPanel(View)과 MacroRunner(Model) 연결
* 스크립트 파일 저장/로드 (비동기 Worker 사용)
* 매크로 실행/정지/일시정지 제어 및 상태 업데이트

## HOW
* ScriptLoadWorker(QThread)를 통한 비동기 로딩
* DTO(MacroScriptData)를 사용한 데이터 전달
"""
from PyQt5.QtCore import QObject, QThread, pyqtSignal
from typing import List, Dict, Any
try:
    import commentjson
except ImportError:
    import json as commentjson

from view.panels.macro_panel import MacroPanel
from model.macro_runner import MacroRunner
from common.dtos import (
    MacroEntry, MacroScriptData, MacroRepeatOption,
    MacroStepEvent, ManualCommand, MacroExecutionRequest
)
from core.logger import logger

class ScriptLoadWorker(QThread):
    """
    비동기 스크립트 로딩 워커
    대용량 JSON 파일 파싱 시 UI 블로킹 방지
    """
    load_finished = pyqtSignal(dict)
    load_failed = pyqtSignal(str)

    def __init__(self, file_path: str):
        """
        ScriptLoadWorker 초기화

        Args:
            file_path (str): 로드할 파일 경로
        """
        super().__init__()
        self.file_path = file_path

    def run(self):
        """
        스크립트 파일 로드 실행
        """
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                data = commentjson.load(f)
            self.load_finished.emit(data)
        except Exception as e:
            self.load_failed.emit(str(e))

class MacroPresenter(QObject):
    """
    매크로 실행 및 관리를 담당하는 Presenter
    """

    def __init__(self, panel: MacroPanel, runner: MacroRunner):
        """
        MacroPresenter 초기화

        Args:
            panel (MacroPanel): 매크로 UI 패널 (View)
            runner (MacroRunner): 매크로 실행 엔진 (Model)
        """
        super().__init__()
        self.panel = panel
        self.runner = runner
        self._load_worker = None

        # View -> Presenter 연결
        self.panel.repeat_start_requested.connect(self.on_repeat_start)
        self.panel.repeat_stop_requested.connect(self.on_repeat_stop)

        # 스크립트 저장/로드 시그널 연결 (MVP: 파일 처리는 Presenter가 담당)
        self.panel.script_save_requested.connect(self.on_script_save)
        self.panel.script_load_requested.connect(self.on_script_load)

        # MacroListWidget의 개별 전송 버튼
        self.panel.macro_list.send_row_requested.connect(self.on_single_send_requested)

        # Model -> Presenter -> View 연결
        self.runner.step_started.connect(self.on_step_started)
        self.runner.step_completed.connect(self.on_step_completed)
        self.runner.macro_finished.connect(self.on_macro_finished)
        self.runner.error_occurred.connect(self.on_error)

    def set_enabled(self, enabled: bool) -> None:
        """
        매크로 제어 활성화/비활성화 (MainPresenter에서 호출)

        Args:
            enabled (bool): 활성화 여부
        """
        self.panel.macro_control.set_controls_enabled(enabled)
        # 리스트의 전송 버튼들도 제어
        self.panel.macro_list.set_send_enabled(enabled)

    def on_script_save(self, script_data: MacroScriptData) -> None:
        """
        스크립트 파일 저장 요청 처리

        Args:
            script_data (MacroScriptData): 저장할 스크립트 데이터
        """
        try:
            self._save_script_file(script_data.file_path, script_data.data)
            self.panel.show_info("Success", "Script saved successfully.")
        except Exception as e:
            logger.error(f"Failed to save script: {e}")
            self.panel.show_error("Save Error", f"Failed to save script:\n{str(e)}")

    def _save_script_file(self, file_path: str, data: dict) -> None:
        """
        [I/O] 파일 저장 수행

        Args:
            file_path (str): 저장할 파일 경로
            data (dict): 저장할 데이터
        """
        with open(file_path, 'w', encoding='utf-8') as f:
            commentjson.dump(data, f, indent=4)
        logger.info(f"Macro script saved to: {file_path}")

    def on_script_load(self, file_path: str) -> None:
        """
        스크립트 파일 로드 요청 처리 (비동기)

        Args:
            file_path (str): 로드할 파일 경로
        """
        logger.debug(f"Starting async script load: {file_path}")

        # 기존 워커가 실행 중이면 대기 (또는 취소)
        if self._load_worker and self._load_worker.isRunning():
            logger.warning("Script loading already in progress.")
            return

        self._load_worker = ScriptLoadWorker(file_path)
        self._load_worker.load_finished.connect(self._on_load_success)
        self._load_worker.load_failed.connect(self._on_load_failed)
        self._load_worker.start()

    def _on_load_success(self, data: dict) -> None:
        """
        로드 성공 시 UI 적용

        Args:
            data (dict): 로드된 스크립트 데이터
        """
        logger.info("Script loaded successfully.")
        self.panel.apply_state(data)
        self._load_worker = None

    def _on_load_failed(self, error_msg: str) -> None:
        """
        로드 실패 시 에러 표시

        Args:
            error_msg (str): 에러 메시지
        """
        logger.error(f"Failed to load script: {error_msg}")
        self.panel.show_error("Load Error", f"Failed to load script:\n{error_msg}")
        self._load_worker = None

    def on_repeat_start(self, indices: List[int], option: MacroRepeatOption) -> None:
        """
        반복 실행 시작 요청 처리

        Logic:
            - UI에서 전체 MacroEntry 리스트를 가져옴 (DTO)
            - 선택된 인덱스의 엔트리만 필터링
            - Runner에 로드 및 시작

        Args:
            indices (List[int]): 실행할 매크로 인덱스 리스트
            option (MacroRepeatOption): 반복 옵션
        """
        if not indices: return

        all_entries = self.panel.macro_list.get_macro_entries()
        selected_entries = []

        for i, entry in enumerate(all_entries):
            if i in indices:
                selected_entries.append(entry)

        if not selected_entries: return

        # 옵션 추출
        option = request.option

        self.runner.load_macro(selected_entries)
        self.runner.start(option.max_runs, option.interval_ms, option.broadcast_enabled)
        self.panel.set_running_state(True)

    def on_repeat_stop(self) -> None:
        """
        반복 실행 중지 요청 처리
        """
        self.runner.stop()

    def on_single_send_requested(self, row_index: int) -> None:
        """
        개별 명령어 전송 요청 처리

        Args:
            row_index (int): 실행할 매크로 인덱스
        """
        if entry:
            manual_command = ManualCommand(
                command=entry.command,
                hex_mode=entry.hex_mode,
                prefix_enabled=entry.prefix_enabled,
                suffix_enabled=entry.suffix_enabled,
                broadcast_enabled=False
            )
            self.runner.send_single_command(manual_command)

    def on_step_started(self, event: MacroStepEvent) -> None:
        """
        스텝 시작 시 처리 (UI 하이라이트 등)

        Args:
            event (MacroStepEvent): 스텝 이벤트 DTO
        """
        # TODO: 현재 실행 중인 행 하이라이트 등의 로직 구현 가능
        pass

    def on_step_completed(self, event: MacroStepEvent) -> None:
        """
        스텝 완료 시 처리 (UI 하이라이트 해제 등)

        Args:
            event (MacroStepEvent): 스텝 이벤트 DTO
        """
        # TODO: 현재 실행 중인 행 하이라이트 해제 등의 로직 구현 가능
        pass

    def on_macro_finished(self) -> None:
        """
        매크로 완료 시 처리 (UI 상태 초기화 등)
        """
        self.panel.set_running_state(False)

    def on_error(self, message: str) -> None:
        """
        에러 발생 시 처리

        Args:
            message (str): 에러 메시지
        """
        logger.error(f"Macro Error: {message}")
        self.panel.set_running_state(False)
