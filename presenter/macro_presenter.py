"""
매크로 프레젠터 모듈

이 모듈은 매크로 View와 Model 사이의 중재자 역할을 수행하는 Presenter입니다.

## WHY
* MVP 패턴을 통해 View와 Model의 결합도를 낮춤
* UI 이벤트를 비즈니스 로직으로 변환하여 전달
* 매크로 실행 상태 및 파일 I/O 결과를 UI에 반영

## WHAT
* MacroPanel(View)의 사용자 입력을 MacroRunner(Model)로 전달
* 파일 저장/로드 로직 수행 (JSON 처리)
* MacroRunner의 실행 상태 및 에러를 UI에 반영
* 단일 명령 전송 요청 처리

## HOW
* PyQt 시그널/슬롯으로 View와 Model 연결
* commentjson(또는 json)을 사용하여 스크립트 파일 처리
* 예외 처리(try-except)를 통해 안전한 파일 I/O 구현
"""
from PyQt5.QtCore import QObject
from typing import List
try:
    import commentjson
except ImportError:
    import json as commentjson

from view.panels.macro_panel import MacroPanel
from model.macro_runner import MacroRunner
from model.macro_entry import MacroEntry
from core.logger import logger

class MacroPresenter(QObject):
    """
    매크로(커맨드 리스트) 실행 및 관리를 담당하는 Presenter
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

    def on_script_save(self, filepath: str, data: dict) -> None:
        """
        스크립트 파일 저장 요청 처리

        Args:
            filepath (str): 저장할 파일 경로
            data (dict): 저장할 데이터 딕셔너리
        """
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                commentjson.dump(data, f, indent=4)

            logger.info(f"Macro script saved to: {filepath}")
            self.panel.show_info("Success", "Script saved successfully.")
        except Exception as e:
            logger.error(f"Failed to save script: {e}")
            self.panel.show_error("Save Error", f"Failed to save script:\n{str(e)}")

    def on_script_load(self, filepath: str) -> None:
        """
        스크립트 파일 로드 요청 처리

        Args:
            filepath (str): 로드할 파일 경로
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = commentjson.load(f)

            # View 업데이트 (상태 복원)
            self.panel.load_state(data)
            logger.info(f"Macro script loaded from: {filepath}")

        except Exception as e:
            logger.error(f"Failed to load script: {e}")
            self.panel.show_error("Load Error", f"Failed to load script:\n{str(e)}")

    def on_repeat_start(self, indices: List[int]) -> None:
        """
        반복 실행 시작 요청 처리

        Args:
            indices (List[int]): 선택된 행 인덱스 리스트
        """
        if not indices:
            return

        # UI에서 설정값 가져오기 (MacroCtrlWidget 상태 조회)
        ctrl_widget = self.panel.marco_ctrl
        loop_count = ctrl_widget.get_repeat_count()
        interval_ms = ctrl_widget.get_interval()

        # 현재 리스트의 데이터를 MacroEntry로 변환
        raw_list = self.panel.macro_list.get_macro_list()
        entries = []

        for i, raw in enumerate(raw_list):
            if i in indices:
                entry = MacroEntry(
                    enabled=raw['enabled'],
                    command=raw['command'],
                    is_hex=raw['hex_mode'],
                    prefix=raw['prefix'],
                    suffix=raw['suffix'],
                    delay_ms=int(raw['delay']) if raw['delay'].isdigit() else 100,
                    # 향후 확장: expect, timeout 등도 여기서 매핑
                )
                entries.append(entry)

        if not entries:
            logger.warning("No entries selected for macro execution")
            return

        # Model에 로드 및 실행
        self.runner.load_macro(entries)
        self.runner.start(loop_count, interval_ms)

        # UI 상태 업데이트 (실행 중 표시)
        self.panel.set_running_state(True)

    def on_repeat_stop(self) -> None:
        """반복 실행 중지 요청 처리"""
        self.runner.stop()

    def on_single_send_requested(self, row_index: int) -> None:
        """
        단일 행 전송 요청 처리

        Args:
            row_index (int): 전송할 행 인덱스
        """
        raw_list = self.panel.macro_list.get_macro_list()
        if 0 <= row_index < len(raw_list):
            raw = raw_list[row_index]
            # 일관성을 위해 Runner의 유틸리티 메서드를 사용하여 전송 요청
            self.runner.request_single_send(
                raw['command'], raw['hex_mode'], raw['prefix'], raw['suffix']
            )

    def on_step_started(self, index: int, entry: MacroEntry) -> None:
        """스텝 시작 시 처리 (UI 하이라이트 등)"""
        pass

    def on_step_completed(self, index: int, success: bool) -> None:
        """스텝 완료 시 처리"""
        pass

    def on_macro_finished(self) -> None:
        """매크로 실행 종료 시 처리 (UI 상태 복구)"""
        self.panel.set_running_state(False)

    def on_error(self, message: str) -> None:
        """
        에러 발생 시 처리

        Args:
            message (str): 에러 메시지
        """
        logger.error(f"Macro Error: {message}")
        self.panel.set_running_state(False)
