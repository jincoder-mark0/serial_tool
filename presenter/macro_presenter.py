"""
매크로 프레젠터 모듈

매크로 실행 및 관리를 담당하는 Presenter입니다.

## WHY
* 매크로 UI 이벤트와 실행 엔진(Model)의 분리 (MVP 패턴)
* 파일 I/O(저장/로드)와 실행 로직의 조율
* 대용량 파일 로딩 시 UI 반응성 확보
* 브로드캐스트 상태 변경을 상위 Presenter에 알림 (UI 동기화용)

## WHAT
* MacroPanel(View)과 MacroRunner(Model) 연결
* 스크립트 파일 저장/로드 (비동기 Worker 사용)
* 매크로 실행/정지/일시정지 제어 및 상태 업데이트
* DTO를 통한 데이터 흐름 제어
* 브로드캐스트 모드 상태 중계

## HOW
* View(Panel)가 제공하는 Facade 메서드를 통해 상태 조회 및 UI 제어
* ScriptLoadWorker(QThread)를 통한 비동기 로딩
* DTO(MacroScriptData, MacroExecutionRequest)를 사용한 데이터 전달
* Signal/Slot을 이용한 이벤트 처리
"""
from typing import List, Dict, Any, Optional, Tuple
try:
    import commentjson
except ImportError:
    import json as commentjson

from PyQt5.QtCore import QObject, QThread, pyqtSignal, Qt

from view.panels.macro_panel import MacroPanel
from model.macro_runner import MacroRunner
from common.dtos import (
    MacroEntry,
    MacroScriptData,
    MacroRepeatOption,
    MacroStepEvent,
    ManualCommand,
    MacroExecutionRequest,
    MacroErrorEvent
)
from core.logger import logger


class ScriptLoadWorker(QThread):
    """
    비동기 스크립트 로딩 워커

    대용량 JSON 파일 파싱 시 UI 블로킹을 방지하기 위해 별도 스레드에서 실행됩니다.
    """
    load_finished = pyqtSignal(dict)
    load_failed = pyqtSignal(str)

    def __init__(self, file_path: str):
        """
        ScriptLoadWorker 초기화

        Args:
            file_path (str): 로드할 파일 경로.
        """
        super().__init__()
        self.file_path = file_path

    def run(self):
        """
        스크립트 파일 로드 실행 (Thread Entry Point)

        Logic:
            - 파일 열기 및 JSON 파싱
            - 성공 시 데이터 방출, 실패 시 에러 메시지 방출
        """
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                data = commentjson.load(f)
            self.load_finished.emit(data)
        except Exception as e:
            self.load_failed.emit(str(e))


class MacroPresenter(QObject):
    """
    매크로 실행 및 관리를 담당하는 Presenter 클래스
    """

    # 브로드캐스트 상태 변경 알림 (MainPresenter가 구독)
    broadcast_changed = pyqtSignal(bool)

    def __init__(self, panel: MacroPanel, runner: MacroRunner):
        """
        MacroPresenter 초기화

        Args:
            panel (MacroPanel): 매크로 UI 패널 (View).
            runner (MacroRunner): 매크로 실행 엔진 (Model).
        """
        super().__init__()
        self.panel = panel
        self.runner = runner
        self._load_worker: Optional[ScriptLoadWorker] = None

        # ---------------------------------------------------------
        # 1. View -> Presenter 연결
        # ---------------------------------------------------------
        # View는 단순히 요청 시그널만 보내고, 로직은 Presenter가 처리
        self.panel.repeat_start_requested.connect(self.on_repeat_start)
        self.panel.repeat_stop_requested.connect(self.on_repeat_stop)
        self.panel.repeat_pause_requested.connect(self.on_repeat_pause)

        # 스크립트 저장/로드 시그널 연결 (MVP: 파일 처리는 Presenter가 담당)
        self.panel.script_save_requested.connect(self.on_script_save)
        self.panel.script_load_requested.connect(self.on_script_load)

        # 개별 전송 버튼 (DTO 수신) - Panel이 중계
        self.panel.send_row_requested.connect(self.on_single_send_requested)

        # 브로드캐스트 체크박스 변경 감지 (Relay)
        self.panel.broadcast_changed.connect(self.broadcast_changed.emit)

        # ---------------------------------------------------------
        # 2. Model -> Presenter -> View 연결
        # ---------------------------------------------------------
        self.runner.step_started.connect(self.on_step_started)
        self.runner.step_completed.connect(self.on_step_completed)
        self.runner.macro_finished.connect(self.on_macro_finished)
        self.runner.error_occurred.connect(self.on_error)

        # 반복 횟수 업데이트 연결
        self.runner.loop_progress.connect(self.on_loop_progress)

    def set_enabled(self, enabled: bool) -> None:
        """
        매크로 제어 활성화/비활성화 상태를 설정합니다 (MainPresenter에서 호출).

        Args:
            enabled (bool): 활성화 여부.
        """
        # Panel이 내부적으로 ControlWidget과 ListWidget의 활성화를 모두 처리해야 함
        self.panel.set_controls_enabled(enabled)

    def is_broadcast_enabled(self) -> bool:
        """
        현재 브로드캐스트 체크박스 상태를 반환합니다.
        (MainPresenter가 버튼 활성화 로직 판단 시 호출)

        Returns:
            bool: 브로드캐스트 활성화 여부.
        """
        return self.panel.is_broadcast_enabled()

    def on_script_save(self, script_data: MacroScriptData) -> None:
        """
        스크립트 파일 저장 요청 처리 핸들러

        Logic:
            - DTO에서 경로와 데이터를 추출하여 파일로 저장
            - 성공/실패 여부를 View에 알림

        Args:
            script_data (MacroScriptData): 저장할 스크립트 데이터 DTO.
        """
        try:
            self._save_script_file(script_data.file_path, script_data.data)
            self.panel.show_info("Success", "Script saved successfully.")
        except Exception as e:
            logger.error(f"Failed to save script: {e}")
            self.panel.show_error("Save Error", f"Failed to save script:\n{str(e)}")

    def _save_script_file(self, file_path: str, data: dict) -> None:
        """
        [I/O] 파일 저장을 실제로 수행합니다.

        Args:
            file_path (str): 저장할 파일 경로.
            data (dict): 저장할 데이터.
        """
        with open(file_path, 'w', encoding='utf-8') as f:
            commentjson.dump(data, f, indent=4)
        logger.info(f"Macro script saved to: {file_path}")

    def on_script_load(self, file_path: str) -> None:
        """
        스크립트 파일 로드 요청 처리 (비동기)

        Logic:
            - 기존 로딩 작업 확인
            - Worker 생성 및 시작
            - 성공/실패 시그널 연결

        Args:
            file_path (str): 로드할 파일 경로.
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
        로드 성공 시 View에 데이터를 적용합니다.

        Args:
            data (dict): 로드된 스크립트 데이터.
        """
        logger.info("Script loaded successfully.")
        self.panel.apply_state(data)
        self._load_worker = None

    def _on_load_failed(self, error_msg: str) -> None:
        """
        로드 실패 시 에러를 표시합니다.

        Args:
            error_msg (str): 에러 메시지.
        """
        logger.error(f"Failed to load script: {error_msg}")
        self.panel.show_error("Load Error", f"Failed to load script:\n{error_msg}")
        self._load_worker = None

    def on_repeat_start(self, request: MacroExecutionRequest) -> None:
        """
        반복 실행 시작 요청 처리 핸들러

        Logic:
            - View에서 전달받은 DTO(`MacroExecutionRequest`)를 사용
            - 전체 엔트리 중 선택된 인덱스의 엔트리만 필터링
            - 원본 행 번호를 유지하기 위해 (RowIndex, Entry) 튜플 생성
            - Runner에 로드 및 시작 명령 전달
            - View 상태 업데이트 (is_repeat=True 명시)

        Args:
            request (MacroExecutionRequest): 실행 요청 DTO (인덱스 목록, 옵션 포함).
        """
        indices = request.indices
        if not indices:
            return

        # View에서 전체 데이터 조회 (Facade Method 사용)
        all_entries = self.panel.get_macro_entries()

        # 실행 계획 생성: (원본 행 번호, 매크로 항목) 튜플의 리스트
        # 이를 통해 Runner가 실행 중인 항목의 원본 위치를 알 수 있음
        execution_plan: List[Tuple[int, MacroEntry]] = []

        for i, entry in enumerate(all_entries):
            if i in indices:
                execution_plan.append((i, entry))

        if not execution_plan:
            return

        # 옵션 추출
        option = request.option

        # Runner 설정 및 시작
        self.runner.load_macro(execution_plan)

        self.runner.start(
            loop_count=option.max_runs,
            interval_ms=option.interval_ms,
            broadcast_enabled=option.broadcast_enabled,
            stop_on_error=option.stop_on_error
        )

        # 반복 모드임을 명시 (is_repeat=True)
        # 이를 통해 UI의 Stop/Pause 버튼이 올바르게 활성화됨
        self.panel.set_running_state(True, is_repeat=True)

    def on_repeat_stop(self) -> None:
        """
        반복 실행 중지 요청 처리 핸들러
        """
        self.runner.stop()

    def on_repeat_pause(self) -> None:
        """
        일시 정지 / 재개 요청 처리 핸들러

        Logic:
            - Runner의 현재 일시정지 상태 확인
            - 상태에 따라 resume() 또는 pause() 호출
        """
        # Runner의 내부 상태(_is_paused)를 확인하여 토글
        if self.runner._is_paused:
            self.runner.resume()
        else:
            self.runner.pause()

    def on_single_send_requested(self, row_index: int, entry: MacroEntry) -> None:
        """
        개별 명령어 전송 요청 처리 핸들러

        Logic:
            - View로부터 전달받은 `MacroEntry` DTO를 `ManualCommand` DTO로 변환
            - Runner의 단일 전송 메서드 호출
            - (참고: 단일 전송은 기본적으로 Broadcast 하지 않음)

        Args:
            row_index (int): 실행할 매크로 인덱스 (로깅용, 로직엔 미사용).
            entry (MacroEntry): 실행할 매크로 엔트리 DTO.
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
        스텝 시작 시 처리 (UI 하이라이트)

        Logic:
            - Model에서 전달된 `event.index`는 원본 테이블의 행 번호임
            - View의 `set_current_row`를 호출하여 해당 행 강조 및 스크롤 이동 (Facade)

        Args:
            event (MacroStepEvent): 스텝 이벤트 DTO.
        """
        self.panel.set_current_row(event.index)

    def on_step_completed(self, event: MacroStepEvent) -> None:
        """
        스텝 완료 시 처리 (UI 하이라이트 해제 등)

        Args:
            event (MacroStepEvent): 스텝 이벤트 DTO.
        """
        # 필요 시 성공/실패 여부를 리스트에 아이콘으로 표시 가능
        pass

    def on_macro_finished(self) -> None:
        """
        매크로 완료 시 처리 (UI 상태 초기화)
        """
        # 종료 시에는 running=False이므로 is_repeat 인자는 기본값(False) 사용
        self.panel.set_running_state(False)
        self.panel.set_current_row(-1) # 하이라이트 제거

    def on_loop_progress(self, current: int, total: int) -> None:
        """
        매크로 반복 횟수 업데이트 핸들러

        Args:
            current (int): 현재 반복 횟수.
            total (int): 전체 반복 횟수 (0=무한).
        """
        self.panel.update_auto_count(current, total)

    def on_error(self, event: MacroErrorEvent) -> None:
        """
        에러 발생 시 처리 핸들러

        Args:
            event (MacroErrorEvent): 매크로 에러 이벤트 DTO.
        """
        logger.error(f"Macro Error: {event.message}")
        self.panel.set_running_state(False)
        self.panel.set_current_row(-1)