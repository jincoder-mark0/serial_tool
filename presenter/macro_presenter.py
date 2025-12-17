"""
매크로 프레젠터 모듈

View와 Model 사이의 중재자 역할을 수행하며, I/O와 Action 메서드를 명확히 분리합니다.

## WHY
* MVP 패턴을 통해 View와 Model의 결합도를 낮춤
* UI 이벤트를 비즈니스 로직으로 변환하여 전달
* 매크로 실행 상태 및 파일 I/O 결과를 UI에 반영
* 대용량 파일 로딩을 비동기 Worker로 처리하여 UI 프리징 방지

## WHAT
* MacroPanel(View)의 사용자 입력을 MacroRunner(Model)로 전달
* 파일 저장/로드 로직 수행 (JSON 처리)
* MacroRunner의 실행 상태 및 에러를 UI에 반영
* 단일 명령 전송 요청 처리

## HOW
* PyQt 시그널/슬롯으로 View와 Model 연결
* commentjson(또는 json)을 사용하여 스크립트 파일 처리
* 예외 처리(try-except)를 통해 안전한 파일 I/O 구현
* DTO를 사용하여 데이터 전송
* QThread 기반 비동기 로딩 (ScriptLoadWorker)
"""
from PyQt5.QtCore import QObject, QThread, pyqtSignal
from typing import List, Dict, Any
try:
    import commentjson
except ImportError:
    import json as commentjson

from view.panels.macro_panel import MacroPanel
from model.macro_runner import MacroRunner
from common.dtos import MacroEntry, MacroScriptData, MacroRepeatOption, MacroStepEvent
from core.logger import logger

class ScriptLoadWorker(QThread):
    """
    비동기 스크립트 로딩 워커
    대용량 JSON 파일 파싱 시 UI 블로킹 방지
    """
    load_finished = pyqtSignal(dict)
    load_failed = pyqtSignal(str)

    def __init__(self, filepath: str):
        """
        ScriptLoadWorker 초기화

        Args:
            filepath (str): 로드할 파일 경로
        """
        super().__init__()
        self.filepath = filepath

    def run(self):
        """
        스크립트 파일 로드 실행
        """
        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
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

        # ---------------------------------------------------------
        # View -> Presenter 연결
        # ---------------------------------------------------------
        self.panel.repeat_start_requested.connect(self.on_repeat_start)
        self.panel.repeat_stop_requested.connect(self.on_repeat_stop)

        # 스크립트 저장/로드 시그널 연결 (MVP: 파일 처리는 Presenter가 담당)
        self.panel.script_save_requested.connect(self.on_script_save)
        self.panel.script_load_requested.connect(self.on_script_load)

        # MacroListWidget의 개별 전송 버튼
        self.panel.macro_list.send_row_requested.connect(self.on_single_send_requested)

        # ---------------------------------------------------------
        # Model -> Presenter -> View 연결
        # ---------------------------------------------------------
        self.runner.step_started.connect(self.on_step_started)
        self.runner.step_completed.connect(self.on_step_completed)
        self.runner.macro_finished.connect(self.on_macro_finished)
        self.runner.error_occurred.connect(self.on_error)

    def on_script_save(self, script_data: MacroScriptData) -> None:
        """
        스크립트 파일 저장 요청 처리

        Args:
            script_data (MacroScriptData): 저장할 스크립트 데이터
        """
        try:
            self._save_script_file(script_data.filepath, script_data.data)
            self.panel.show_info("Success", "Script saved successfully.")
        except Exception as e:
            logger.error(f"Failed to save script: {e}")
            self.panel.show_error("Save Error", f"Failed to save script:\n{str(e)}")

    def _save_script_file(self, filepath: str, data: dict) -> None:
        """
        [I/O] 파일 저장 수행

        Args:
            filepath (str): 저장할 파일 경로
            data (dict): 저장할 데이터
        """
        with open(filepath, 'w', encoding='utf-8') as f:
            commentjson.dump(data, f, indent=4)
        logger.info(f"Macro script saved to: {filepath}")

    def on_script_load(self, filepath: str) -> None:
        """
        스크립트 파일 로드 요청 처리 (비동기)

        Args:
            filepath (str): 로드할 파일 경로
        """
        logger.debug(f"Starting async script load: {filepath}")

        # 기존 워커가 실행 중이면 대기 (또는 취소)
        if self._load_worker and self._load_worker.isRunning():
            logger.warning("Script loading already in progress.")
            return

        self._load_worker = ScriptLoadWorker(filepath)
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

        Args:
            indices (List[int]): 실행할 매크로 인덱스 리스트
            option (MacroRepeatOption): 반복 옵션
        """
        if not indices: return

        raw_list = self.panel.macro_list.export_macros()
        entries = []
        for i, raw in enumerate(raw_list):
            if i in indices:
                delay = int(raw['delay']) if raw['delay'].isdigit() else 100
                entry = MacroEntry(
                    enabled=raw['enabled'],
                    command=raw['command'],
                    is_hex=raw['hex_mode'],
                    prefix=raw['prefix'],
                    suffix=raw['suffix'],
                    delay_ms=delay
                )
                entries.append(entry)

        if not entries: return

        self.runner.load_macro(entries)
        self.runner.start(option.max_runs, option.interval_ms, option.is_broadcast)
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
        raw_list = self.panel.macro_list.export_macros()
        if 0 <= row_index < len(raw_list):
            raw = raw_list[row_index]
            self.runner.send_single_command(
                raw['command'], raw['hex_mode'], raw['prefix'], raw['suffix']
            )

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
