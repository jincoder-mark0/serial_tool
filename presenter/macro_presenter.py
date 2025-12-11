from PyQt5.QtCore import QObject
from typing import List, Dict, Any

from view.panels.macro_panel import MacroPanel
from model.macro_runner import MacroRunner
from model.macro_entry import MacroEntry
from core.logger import logger

class MacroPresenter(QObject):
    """
    매크로(커맨드 리스트) 실행 및 관리를 담당하는 Presenter
    """
    def __init__(self, panel: MacroPanel, runner: MacroRunner):
        super().__init__()
        self.panel = panel
        self.runner = runner
        
        # View -> Presenter
        self.panel.repeat_start_requested.connect(self.on_repeat_start)
        self.panel.repeat_stop_requested.connect(self.on_repeat_stop)
        
        # MacroListWidget의 개별 전송 버튼
        self.panel.macro_list.send_row_requested.connect(self.on_single_send_requested)
        
        # Model -> Presenter -> View
        self.runner.step_started.connect(self.on_step_started)
        self.runner.step_completed.connect(self.on_step_completed)
        self.runner.macro_finished.connect(self.on_macro_finished)
        self.runner.error_occurred.connect(self.on_error)
        
    def on_repeat_start(self, indices: List[int]):
        """반복 실행 시작 요청 처리"""
        if not indices:
            return
            
        # UI에서 설정값 가져오기
        # MacroCtrlWidget의 상태를 읽어야 함
        ctrl_widget = self.panel.marco_ctrl
        loop_count = ctrl_widget.get_repeat_count()
        interval_ms = ctrl_widget.get_interval()
        
        # 현재 리스트의 데이터를 MacroEntry로 변환
        raw_list = self.panel.macro_list.get_macro_list()
        entries = []
        
        for i, raw in enumerate(raw_list):
            # 선택된 항목만 실행할지, 전체를 실행할지 결정해야 함
            # 일반적으로 Repeat Start는 '체크된 항목'만 실행하는 것이 직관적
            if i in indices:
                entry = MacroEntry(
                    enabled=raw['enabled'],
                    command=raw['command'],
                    is_hex=raw['hex_mode'],
                    prefix=raw['prefix'],
                    suffix=raw['suffix'],
                    delay_ms=int(raw['delay']) if raw['delay'].isdigit() else 100
                )
                entries.append(entry)
                
        if not entries:
            logger.warning("No entries selected for macro execution")
            return
            
        self.runner.load_macro(entries)
        self.runner.start(loop_count, interval_ms)
        
        # UI 상태 업데이트
        self.panel.set_running_state(True)
        
    def on_repeat_stop(self):
        """반복 실행 중지 요청 처리"""
        self.runner.stop()
        
    def on_single_send_requested(self, row_index: int):
        """단일 행 전송 요청 처리"""
        # 해당 행의 데이터만 가져와서 1회 실행
        raw_list = self.panel.macro_list.get_macro_list()
        if 0 <= row_index < len(raw_list):
            raw = raw_list[row_index]
            entry = MacroEntry(
                enabled=True, # 강제 활성화
                command=raw['command'],
                is_hex=raw['hex_mode'],
                prefix=raw['prefix'],
                suffix=raw['suffix'],
                delay_ms=0
            )
            
            # Runner를 통하지 않고 직접 전송 요청 시그널을 발생시키거나
            # Runner에 single_step 메서드를 추가할 수 있음.
            # 여기서는 Runner의 send_requested 시그널을 재사용하기 위해
            # Runner에 임시 리스트를 로드하고 1회 실행할 수도 있지만,
            # 단순히 send_requested 시그널을 직접 emit하는 것이 나을 수 있음.
            # 하지만 Runner가 중앙에서 제어하는 것이 좋으므로, 
            # Runner.send_requested를 emit하도록 유도하거나 MainPresenter로 직접 전달.
            
            # 가장 깔끔한 방법: Runner.send_requested와 동일한 시그널을 MainPresenter가 연결하고 있으므로
            # 여기서도 동일한 시그널을 emit하면 됨.
            # 하지만 MacroPresenter는 send_requested 시그널이 없음.
            # Runner를 통해 전송하는 것이 일관성이 있음.
            
            self.runner.send_requested.emit(
                entry.command, entry.is_hex, entry.prefix, entry.suffix
            )

    def on_step_started(self, index: int, entry: MacroEntry):
        """스텝 시작 시 UI 업데이트 (예: 하이라이트)"""
        pass

    def on_step_completed(self, index: int, success: bool):
        """스텝 완료 시 UI 업데이트"""
        pass

    def on_macro_finished(self):
        """매크로 종료 시 UI 업데이트"""
        self.panel.set_running_state(False)

    def on_error(self, message: str):
        """에러 발생 시 처리"""
        logger.error(f"Macro Error: {message}")
        self.panel.set_running_state(False)
